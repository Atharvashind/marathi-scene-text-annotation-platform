"""
finetune.py  —  Fine-tune PARseq Marathi recogniser on Marathi25K
==================================================================
Step 1 : Convert PNG + CSV/TXT dataset to LMDB format
Step 2 : Load the base marathi.ckpt checkpoint
Step 3 : Build DataLoaders
Step 4 : Fine-tune and save the best model

Usage:
    D:\\AUS_TEXT\\train_env\\Scripts\\python.exe D:\\AUS_TEXT\\finetune.py

Expected time (Quadro P620, 2 GB VRAM):  ~2-4 hours for 10 epochs
Output: D:\\AUS_TEXT\\marathi_finetuned.ckpt
"""

import sys, os, csv, io, time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DATASET_ROOT   = Path("D:/AUS_TEXT/Marathi25K")
INDIC_PATH     = Path("D:/AUS_TEXT/IndicPhotoOCR")
LMDB_OUT       = Path("D:/AUS_TEXT/marathi25k_lmdb")
CHECKPOINT_IN  = INDIC_PATH / "IndicPhotoOCR/recognition/models/marathi.ckpt"
CHECKPOINT_OUT = Path("D:/AUS_TEXT/marathi_finetuned.ckpt")

EPOCHS        = 10
BATCH_SIZE    = 32    # safe for 2 GB VRAM
LR            = 1e-4
MAX_LABEL_LEN = 25
NUM_WORKERS   = 0     # keep 0 on Windows

# ── Environment setup ─────────────────────────────────────────────────────────
sys.path.insert(0, str(INDIC_PATH))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import warnings; warnings.filterwarnings("ignore")

import torch

print("=" * 60)
print("  PARseq Marathi Fine-tuning")
print("=" * 60)
print(f"  Device     : {'CUDA — ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
print(f"  Epochs     : {EPOCHS}   |   Batch size : {BATCH_SIZE}")
print(f"  Checkpoint : {CHECKPOINT_IN.name}")
print()
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# ── Patch PyTorch 2.6 weights_only default ────────────────────────────────────
import lightning_fabric.utilities.cloud_io as _ci
_orig_ci = _ci._load
def _patched_load(p, map_location=None, weights_only=True):
    return _orig_ci(p, map_location=map_location, weights_only=False)
_ci._load = _patched_load
torch.serialization.add_safe_globals([getattr])

# ── Pre-load VIT processor before shapely (DLL conflict fix) ──────────────────
from transformers import AutoImageProcessor as _AIP
_proc = _AIP.from_pretrained("google/vit-base-patch16-224-in21k", use_fast=False)
_orig_aip = _AIP.from_pretrained
def _cached_aip(m, **kw):
    if "vit-base-patch16-224-in21k" in str(m): return _proc
    return _orig_aip(m, **kw)
_AIP.from_pretrained = _cached_aip


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Build LMDB datasets
# ════════════════════════════════════════════════════════════════════════════

import lmdb
from PIL import Image

TRAIN_LMDB = LMDB_OUT / "train"
VAL_LMDB   = LMDB_OUT / "val"


def write_lmdb(out_path: Path, pairs: list):
    """Write [(img_path, label), ...] to LMDB."""
    out_path.mkdir(parents=True, exist_ok=True)
    map_size = max(len(pairs) * 15 * 1024, 20 * 1024 * 1024)
    env = lmdb.open(str(out_path), map_size=map_size, readonly=False, meminit=False)
    count = 0
    with env.begin(write=True) as txn:
        for idx, (img_path, label) in enumerate(pairs, start=1):
            try:
                img = Image.open(img_path).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                txn.put(f"image-{idx:09d}".encode(), buf.getvalue())
                txn.put(f"label-{idx:09d}".encode(), label.encode("utf-8"))
                count += 1
            except Exception as e:
                print(f"  skip {img_path.name}: {e}")
        txn.put(b"num-samples", str(count).encode())
    env.close()
    return count


# ── Train LMDB ────────────────────────────────────────────────────────────────
if not TRAIN_LMDB.exists():
    print("Step 1a: Building train LMDB ...")
    train_pairs = []
    with open(DATASET_ROOT / "Train" / "Trainlabels.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)   # header: image_path,text_label
        next(reader)   # junk row: Data_Column,Data_Column
        for row in reader:
            if len(row) < 2: continue
            fname = Path(row[0]).name
            label = row[1].strip()
            img_p = DATASET_ROOT / "Train" / "trainimages" / fname
            if img_p.exists() and label and len(label) <= MAX_LABEL_LEN:
                train_pairs.append((img_p, label))
    n = write_lmdb(TRAIN_LMDB, train_pairs)
    print(f"  Written {n} samples → {TRAIN_LMDB}")
else:
    print("Step 1a: Train LMDB exists — skipping.")

# ── Val LMDB ──────────────────────────────────────────────────────────────────
if not VAL_LMDB.exists():
    print("Step 1b: Building val LMDB ...")
    img_lines   = [l.strip() for l in open(DATASET_ROOT/"val"/"val_images.txt", encoding="utf-8") if l.strip()]
    label_lines = [l.strip() for l in open(DATASET_ROOT/"val"/"val_labels.txt", encoding="utf-8") if l.strip()]
    val_pairs   = [
        (DATASET_ROOT / "val" / "images" / Path(img).name, lbl)
        for img, lbl in zip(img_lines, label_lines)
        if (DATASET_ROOT / "val" / "images" / Path(img).name).exists() and lbl.strip()
    ]
    n = write_lmdb(VAL_LMDB, val_pairs)
    print(f"  Written {n} samples → {VAL_LMDB}")
else:
    print("Step 1b: Val LMDB exists — skipping.")

print()


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Load base model
# ════════════════════════════════════════════════════════════════════════════

print("Step 2: Loading base model ...")

from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint

if not CHECKPOINT_IN.exists():
    from IndicPhotoOCR.recognition.parseq_recogniser import model_info
    import requests
    print("  Downloading marathi.ckpt ...")
    CHECKPOINT_IN.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(model_info["marathi"]["url"], stream=True)
    with open(CHECKPOINT_IN, "wb") as f:
        for chunk in r.iter_content(8192): f.write(chunk)

model = load_from_checkpoint(str(CHECKPOINT_IN)).to(device)
hp    = model.hparams
print(f"  Loaded  : {CHECKPOINT_IN.name}")
print(f"  Charset : {len(hp.charset_train)} chars   |   img_size: {hp.img_size}")
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
            T.RandomApply([T.ColorJitter(0.3, 0.3, 0.3, 0.1)], p=0.5),
            T.RandomGrayscale(p=0.1),
            T.RandomApply([T.GaussianBlur(3)], p=0.2),
        ]
    ops += [
        T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(0.5, 0.5),
    ]
    return T.Compose(ops)


def collate_fn(batch):
    """Stack image tensors; keep labels as list of strings."""
    imgs, labels = zip(*batch)
    return torch.stack(imgs, 0), list(labels)


# normalize_unicode=False is CRITICAL — NFKD strips Devanagari diacritics
DS_KWARGS = dict(
    charset=hp.charset_train,
    max_label_len=hp.max_label_length,
    min_image_dim=0,
    remove_whitespace=True,
    normalize_unicode=False,
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
    print("ERROR: Train dataset is empty — check LMDB and charset.")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — Fine-tune
# ════════════════════════════════════════════════════════════════════════════

print("Step 4: Fine-tuning ...")
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
    # ── Train pass ────────────────────────────────────────────────────────────
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

        if step % 100 == 0 or step == len(train_loader):
            print(f"  Ep {epoch}/{EPOCHS} | step {step:4d}/{len(train_loader)} "
                  f"| loss {total_loss/step:.4f}", flush=True)

    avg_loss = total_loss / len(train_loader)

    # ── Validation pass ───────────────────────────────────────────────────────
    model.eval()
    correct = total = 0

    if len(val_loader) > 0:
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
    else:
        val_acc = 0.0
        print("  (No validation samples — skipping val pass)")

    elapsed = time.time() - t_ep
    total_elapsed = (time.time() - t_start) / 60

    print(f"\n  ── Epoch {epoch}/{EPOCHS} ──")
    print(f"     Train loss : {avg_loss:.4f}")
    print(f"     Val acc    : {val_acc:.2f}%  ({correct}/{total})")
    print(f"     Time       : {elapsed:.1f}s this epoch | {total_elapsed:.1f}min total\n")

    # Save best
    if val_acc > best_val_acc or (len(val_loader) == 0 and epoch == EPOCHS):
        best_val_acc = val_acc
        torch.save(
            {"state_dict": model.state_dict(),
             "hyper_parameters": dict(model.hparams)},
            str(CHECKPOINT_OUT),
        )
        print(f"     ★ Saved best → {CHECKPOINT_OUT.name}\n")


# ════════════════════════════════════════════════════════════════════════════
# Done
# ════════════════════════════════════════════════════════════════════════════

total_min = (time.time() - t_start) / 60
print("=" * 60)
print("  Fine-tuning complete!")
print(f"  Best Val Accuracy : {best_val_acc:.2f}%")
print(f"  Total time        : {total_min:.1f} minutes")
print(f"  Checkpoint saved  : {CHECKPOINT_OUT}")
print()
print("  To use the fine-tuned model:")
print(f"    1. Rename  {CHECKPOINT_IN}  →  marathi_original.ckpt")
print(f"    2. Copy    {CHECKPOINT_OUT}")
print(f"       to     {CHECKPOINT_IN}")
print("    3. Restart the annotation platform backend")
print("=" * 60)
