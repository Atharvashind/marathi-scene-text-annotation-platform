"""
finetune.py  —  Sequential Fine-tuning: MahaSTR on top of marathi_finetuned.ckpt
==================================================================================

Training chain:
  marathi.ckpt  (original, ~363 MB)
       ↓  fine-tune on Marathi25K (17,500 samples)  [already done]
  marathi_finetuned.ckpt  (94.96% word acc on Marathi25K test set)
       ↓  fine-tune on MahaSTR   (4,303 samples)    [THIS SCRIPT]
  marathi_combined.ckpt

Why sequential and not combined?
  - The model already specialised on Marathi signboard text from Marathi25K.
  - Fine-tuning again on MahaSTR teaches it new vocabulary and fonts from that
    dataset WITHOUT forgetting what it learned — this is curriculum learning.
  - Mixing both datasets in one pass would dilute the Marathi25K signal.

Usage:
    D:\\AUS_TEXT\\train_env\\Scripts\\python.exe D:\\AUS_TEXT\\finetune.py

Expected time:  ~40-60 min on Quadro P620 (2 GB VRAM) for 10 epochs
                (4,303 samples is small — trains fast)
Output:         D:\\AUS_TEXT\\marathi_combined.ckpt
"""

import sys, os, csv, io, time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
MAHASTR_ROOT    = Path("D:/AUS_TEXT/MahaSTR/dataset")
INDIC_PATH      = Path("D:/AUS_TEXT/IndicPhotoOCR")
LMDB_OUT        = Path("D:/AUS_TEXT/mahastr_lmdb")          # separate LMDB, not combined
CHECKPOINT_IN   = Path("D:/AUS_TEXT/marathi_finetuned.ckpt") # start from the Marathi25K checkpoint
CHECKPOINT_OUT  = Path("D:/AUS_TEXT/marathi_combined.ckpt")

EPOCHS        = 15          # more epochs — small dataset trains fast
BATCH_SIZE    = 32          # safe for 2 GB VRAM
LR            = 5e-5        # lower LR — we're fine-tuning a fine-tuned model
MAX_LABEL_LEN = 25
MAX_IMG_DIM   = 800         # skip whole-scene images
NUM_WORKERS   = 0           # Windows: keep 0

# ── Environment setup ─────────────────────────────────────────────────────────
sys.path.insert(0, str(INDIC_PATH))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import warnings; warnings.filterwarnings("ignore")

import torch

print("=" * 60)
print("  Sequential Fine-tuning: MahaSTR")
print("=" * 60)
print(f"  Base model : {CHECKPOINT_IN.name}  (Marathi25K fine-tuned, 94.96% acc)")
print(f"  Dataset    : MahaSTR only ({MAHASTR_ROOT})")
print(f"  Device     : {'CUDA — ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
print(f"  Epochs     : {EPOCHS}  |  Batch: {BATCH_SIZE}  |  LR: {LR}")
print(f"  Output     : {CHECKPOINT_OUT.name}")
print()

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# ── Patches ───────────────────────────────────────────────────────────────────
import lightning_fabric.utilities.cloud_io as _ci
_orig_ci = _ci._load
def _patched_load(p, map_location=None, weights_only=True):
    return _orig_ci(p, map_location=map_location, weights_only=False)
_ci._load = _patched_load
torch.serialization.add_safe_globals([getattr])

from transformers import AutoImageProcessor as _AIP
_proc = _AIP.from_pretrained("google/vit-base-patch16-224-in21k", use_fast=False)
_orig_aip = _AIP.from_pretrained
def _cached_aip(m, **kw):
    if "vit-base-patch16-224-in21k" in str(m): return _proc
    return _orig_aip(m, **kw)
_AIP.from_pretrained = _cached_aip


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Build LMDB from MahaSTR only
# ════════════════════════════════════════════════════════════════════════════

import lmdb
from PIL import Image

TRAIN_LMDB = LMDB_OUT / "train"
VAL_LMDB   = LMDB_OUT / "val"


def write_lmdb(out_path: Path, pairs: list, label: str = "") -> tuple:
    out_path.mkdir(parents=True, exist_ok=True)
    map_size = max(len(pairs) * 120 * 1024, 30 * 1024 * 1024)
    env = lmdb.open(str(out_path), map_size=map_size, readonly=False, meminit=False)
    count = skipped = 0
    with env.begin(write=True) as txn:
        for img_path, lbl in pairs:
            try:
                img = Image.open(img_path).convert("RGB")
                w, h = img.size
                if w > MAX_IMG_DIM or h > MAX_IMG_DIM:
                    skipped += 1
                    continue
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                idx = count + 1
                txn.put(f"image-{idx:09d}".encode(), buf.getvalue())
                txn.put(f"label-{idx:09d}".encode(), lbl.encode("utf-8"))
                count += 1
            except Exception:
                skipped += 1
        txn.put(b"num-samples", str(count).encode())
    env.close()
    return count, skipped


def load_mahastr_csv(csv_path: Path, images_dir: Path) -> list:
    pairs = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fname = row["image"].strip()
            lbl   = row["label"].strip()
            img_p = images_dir / fname
            if img_p.exists() and lbl and 1 <= len(lbl) <= MAX_LABEL_LEN:
                pairs.append((img_p, lbl))
    return pairs


if not TRAIN_LMDB.exists():
    print("Step 1a: Building MahaSTR train LMDB ...")
    train_pairs = load_mahastr_csv(
        MAHASTR_ROOT / "train" / "train.csv",
        MAHASTR_ROOT / "train" / "images"
    )
    n, sk = write_lmdb(TRAIN_LMDB, train_pairs)
    print(f"  Loaded  : {len(train_pairs):,} pairs from CSV")
    print(f"  Written : {n:,} samples  ({sk} skipped — large scene images)")
else:
    print("Step 1a: Train LMDB exists — skipping.")

if not VAL_LMDB.exists():
    print("Step 1b: Building MahaSTR val LMDB ...")
    val_pairs = load_mahastr_csv(
        MAHASTR_ROOT / "val" / "val.csv",
        MAHASTR_ROOT / "val" / "images"
    )
    n, sk = write_lmdb(VAL_LMDB, val_pairs)
    print(f"  Loaded  : {len(val_pairs):,} pairs from CSV")
    print(f"  Written : {n:,} samples  ({sk} skipped)")
else:
    print("Step 1b: Val LMDB exists — skipping.")

print()


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Load marathi_finetuned.ckpt
# ════════════════════════════════════════════════════════════════════════════

print("Step 2: Loading base checkpoint ...")
from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint

if not CHECKPOINT_IN.exists():
    print(f"ERROR: {CHECKPOINT_IN} not found.")
    print("Run the Marathi25K fine-tuning first, then re-run this script.")
    sys.exit(1)

model = load_from_checkpoint(str(CHECKPOINT_IN)).to(device)
hp    = model.hparams
print(f"  Loaded  : {CHECKPOINT_IN.name}")
print(f"  Charset : {len(hp.charset_train)} chars  |  img_size: {hp.img_size}")
print(f"  Starting from Marathi25K weights (94.96% word accuracy baseline)")
print()


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — DataLoaders
# ════════════════════════════════════════════════════════════════════════════

print("Step 3: Building data loaders ...")

from IndicPhotoOCR.utils.strhub.data.dataset import LmdbDataset
from torch.utils.data import DataLoader
from torchvision import transforms as T


def make_transform(augment=False):
    ops = []
    if augment:
        ops += [
            T.RandomApply([T.ColorJitter(0.4, 0.4, 0.4, 0.15)], p=0.6),
            T.RandomGrayscale(p=0.15),
            T.RandomApply([T.GaussianBlur(3)], p=0.25),
            T.RandomApply([T.RandomAffine(degrees=3, translate=(0.05, 0.05))], p=0.3),
        ]
    ops += [
        T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(0.5, 0.5),
    ]
    return T.Compose(ops)


def collate_fn(batch):
    imgs, labels = zip(*batch)
    return torch.stack(imgs, 0), list(labels)


DS_KWARGS = dict(
    charset=hp.charset_train,
    max_label_len=hp.max_label_length,
    min_image_dim=0,
    remove_whitespace=True,
    normalize_unicode=False,   # CRITICAL — NFKD strips Devanagari diacritics
    unlabelled=False,
)

train_ds = LmdbDataset(str(TRAIN_LMDB), **DS_KWARGS, transform=make_transform(augment=True))
val_ds   = LmdbDataset(str(VAL_LMDB),   **DS_KWARGS, transform=make_transform(augment=False))

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=NUM_WORKERS, pin_memory=True, collate_fn=collate_fn)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False,
                          num_workers=NUM_WORKERS, pin_memory=True, collate_fn=collate_fn)

print(f"  Train : {len(train_ds):,} samples → {len(train_loader):,} batches/epoch")
print(f"  Val   : {len(val_ds):,} samples → {len(val_loader):,} batches")
print()

if len(train_ds) == 0:
    print("ERROR: Train dataset is empty. Delete the LMDB folder and re-run.")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — Fine-tune
# ════════════════════════════════════════════════════════════════════════════

print("Step 4: Fine-tuning on MahaSTR ...")
print(f"  {EPOCHS} epochs × {len(train_loader)} batches = {EPOCHS * len(train_loader):,} steps")
print()

optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=LR,
    steps_per_epoch=len(train_loader), epochs=EPOCHS, pct_start=0.1,
)

best_val_acc = 0.0
t_start = time.time()

for epoch in range(1, EPOCHS + 1):

    # ── Train ──────────────────────────────────────────────────────────────────
    model.train()
    total_loss = 0.0
    t_ep = time.time()

    for step, (imgs, labels) in enumerate(train_loader, 1):
        imgs = imgs.to(device)
        optimizer.zero_grad()
        _logits, loss, _n = model.forward_logits_loss(imgs, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
        scheduler.step()
        total_loss += loss.item()

        if step % 50 == 0 or step == len(train_loader):
            print(f"  Ep {epoch}/{EPOCHS} | step {step:3d}/{len(train_loader)} "
                  f"| loss {total_loss/step:.4f}", flush=True)

    avg_loss = total_loss / len(train_loader)

    # ── Validate ────────────────────────────────────────────────────────────────
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs = imgs.to(device)
            logits = model(imgs)
            probs  = logits.softmax(-1)
            preds, _ = model.tokenizer.decode(probs)
            for pred, true in zip(preds, labels):
                if model.charset_adapter(pred).strip() == true.strip():
                    correct += 1
                total += 1
    val_acc = correct / total * 100 if total else 0.0

    ep_time = time.time() - t_ep
    tot_min = (time.time() - t_start) / 60
    eta_min = (EPOCHS - epoch) * ep_time / 60

    print(f"\n  ── Epoch {epoch}/{EPOCHS} ──")
    print(f"     Train loss : {avg_loss:.4f}")
    print(f"     Val acc    : {val_acc:.2f}%  ({correct}/{total})")
    print(f"     Time       : {ep_time:.1f}s  |  total {tot_min:.1f}min  |  ETA ~{eta_min:.0f}min")

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        import pytorch_lightning as pl
        torch.save({
            "state_dict":                model.state_dict(),
            "hyper_parameters":          dict(model.hparams),
            "pytorch-lightning_version": pl.__version__,
        }, str(CHECKPOINT_OUT))
        print(f"     ★ New best! Saved → {CHECKPOINT_OUT.name}")
    print()


# ════════════════════════════════════════════════════════════════════════════
# Done
# ════════════════════════════════════════════════════════════════════════════

total_min = (time.time() - t_start) / 60
print("=" * 60)
print("  Fine-tuning complete!")
print()
print(f"  Training chain summary:")
print(f"    marathi.ckpt                 (original PARseq)")
print(f"    └─ marathi_finetuned.ckpt    (+ Marathi25K, 94.96% acc)")
print(f"       └─ marathi_combined.ckpt  (+ MahaSTR, this run)")
print()
print(f"  Best Val Accuracy : {best_val_acc:.2f}%")
print(f"  Total time        : {total_min:.1f} minutes")
print(f"  Saved to          : {CHECKPOINT_OUT}")
print()
print("  To deploy:")
print(f"    1. Rename  D:\\AUS_TEXT\\IndicPhotoOCR\\...\\models\\marathi.ckpt")
print(f"               → marathi_finetuned_only.ckpt  (backup)")
print(f"    2. Copy    {CHECKPOINT_OUT.name}")
print(f"               → ...\\models\\marathi.ckpt")
print(f"    3. Restart the annotation platform backend.")
print("=" * 60)
