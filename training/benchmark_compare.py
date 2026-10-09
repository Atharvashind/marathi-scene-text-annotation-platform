"""
benchmark_compare.py
====================
Runs all three checkpoints on the Marathi25K test set AND MahaSTR test set
and prints a side-by-side comparison.

  1. marathi.ckpt           — original (Marathi25K baseline)
  2. marathi_finetuned.ckpt — after Marathi25K fine-tuning
  3. marathi_combined.ckpt  — after sequential MahaSTR fine-tuning (this run)
"""
import sys, os, csv, time
from pathlib import Path

INDIC_PATH   = Path("D:/AUS_TEXT/IndicPhotoOCR")
M25K_TEST_IMG = Path("D:/AUS_TEXT/Marathi25K/Test/testimages")
M25K_TEST_CSV = Path("D:/AUS_TEXT/Marathi25K/Test/Testlabels.csv")
MAHA_TEST_IMG = Path("D:/AUS_TEXT/MahaSTR/dataset/test/images")
MAHA_TEST_CSV = Path("D:/AUS_TEXT/MahaSTR/dataset/test/test.csv")
MAX_TEST      = None   # set to e.g. 500 to run a quick subset

CHECKPOINTS = [
    ("Original",    Path("D:/AUS_TEXT/IndicPhotoOCR/IndicPhotoOCR/recognition/models/marathi_original.ckpt")),
    ("Marathi25K",  Path("D:/AUS_TEXT/marathi_finetuned.ckpt")),
    ("Combined",    Path("D:/AUS_TEXT/marathi_combined.ckpt")),
]

sys.path.insert(0, str(INDIC_PATH))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import warnings; warnings.filterwarnings("ignore")

import torch
from torchvision import transforms as T
from PIL import Image

print("=" * 70)
print("  Marathi OCR Benchmark — Three-Way Model Comparison")
print("=" * 70)
print(f"  Device : {'CUDA — ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
print()

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# ── Patches ───────────────────────────────────────────────────────────────────
import lightning_fabric.utilities.cloud_io as _ci
_orig = _ci._load
def _p(p, map_location=None, weights_only=True): return _orig(p, map_location=map_location, weights_only=False)
_ci._load = _p
torch.serialization.add_safe_globals([getattr])

from transformers import AutoImageProcessor as _AIP
_proc = _AIP.from_pretrained("google/vit-base-patch16-224-in21k", use_fast=False)
_orig_aip = _AIP.from_pretrained
def _cached(m, **kw):
    if "vit-base-patch16-224-in21k" in str(m): return _proc
    return _orig_aip(m, **kw)
_AIP.from_pretrained = _cached

# ── Load test sets ────────────────────────────────────────────────────────────

def load_m25k(csv_path, images_dir):
    pairs = []
    with open(csv_path, encoding="utf-8") as f:
        r = csv.reader(f); next(r); next(r)
        for row in r:
            if len(row) < 2: continue
            p = images_dir / Path(row[0]).name
            if p.exists() and row[1].strip():
                pairs.append((p, row[1].strip()))
    return pairs

def load_mahastr(csv_path, images_dir):
    pairs = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = images_dir / row["image"].strip()
            lbl = row["label"].strip()
            if p.exists() and lbl:
                pairs.append((p, lbl))
    return pairs

m25k_pairs  = load_m25k(M25K_TEST_CSV, M25K_TEST_IMG)
maha_pairs  = load_mahastr(MAHA_TEST_CSV, MAHA_TEST_IMG)
if MAX_TEST:
    m25k_pairs = m25k_pairs[:MAX_TEST]
    maha_pairs = maha_pairs[:MAX_TEST]

print(f"  Marathi25K test : {len(m25k_pairs):,} samples")
print(f"  MahaSTR test    : {len(maha_pairs):,} samples")
print()

# ── Inference function ────────────────────────────────────────────────────────

from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint
from jiwer import cer as jiwer_cer

def run_benchmark(ckpt_path: Path, pairs: list, label: str) -> dict:
    print(f"  Loading {ckpt_path.name} ...", flush=True)
    model = load_from_checkpoint(str(ckpt_path)).to(device).eval()
    hp    = model.hparams
    transform = T.Compose([
        T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
        T.ToTensor(), T.Normalize(0.5, 0.5),
    ])

    correct = total = 0
    total_cer = 0.0
    t0 = time.time()

    with torch.no_grad():
        for i, (img_path, true_label) in enumerate(pairs):
            if i % 500 == 0 and i > 0:
                print(f"    {i}/{len(pairs)} ...", flush=True)
            try:
                img    = Image.open(img_path).convert("RGB")
                tensor = transform(img).unsqueeze(0).to(device)
                logits = model(tensor)
                probs  = logits.softmax(-1)
                preds, _ = model.tokenizer.decode(probs)
                pred = model.charset_adapter(preds[0])
            except Exception:
                pred = ""

            if pred.strip() == true_label.strip():
                correct += 1
            try:
                total_cer += jiwer_cer(true_label, pred if pred else " ")
            except Exception:
                total_cer += 1.0
            total += 1

    elapsed = time.time() - t0
    word_acc = correct / total * 100 if total else 0
    avg_cer  = total_cer / total * 100 if total else 0
    print(f"    Done in {elapsed:.1f}s  →  {word_acc:.2f}% acc", flush=True)

    # Free GPU memory before loading next model
    del model
    torch.cuda.empty_cache()

    return {"word_acc": word_acc, "avg_cer": avg_cer,
            "correct": correct, "total": total, "time": elapsed}


# ── Run all checkpoints on both test sets ─────────────────────────────────────
results = {}

for name, ckpt_path in CHECKPOINTS:
    if not ckpt_path.exists():
        print(f"  SKIP {name}: {ckpt_path.name} not found")
        continue
    print(f"\n{'─'*50}")
    print(f"  Model: {name}  ({ckpt_path.name})")
    print(f"{'─'*50}")
    print("  → Marathi25K test set:")
    r_m25k = run_benchmark(ckpt_path, m25k_pairs, name)
    print("  → MahaSTR test set:")
    r_maha = run_benchmark(ckpt_path, maha_pairs, name)
    results[name] = {"m25k": r_m25k, "maha": r_maha}


# ── Print comparison table ────────────────────────────────────────────────────
print()
print("=" * 70)
print("  RESULTS SUMMARY")
print("=" * 70)
print()

header  = f"{'Model':<15}  {'Marathi25K Acc':>15}  {'Marathi25K CER':>15}  {'MahaSTR Acc':>12}  {'MahaSTR CER':>12}"
divider = "─" * len(header)
print(header)
print(divider)

for name, r in results.items():
    m = r["m25k"]; h = r["maha"]
    print(f"  {name:<13}  {m['word_acc']:>13.2f}%  {m['avg_cer']:>13.2f}%  "
          f"{h['word_acc']:>10.2f}%  {h['avg_cer']:>10.2f}%")

print(divider)
print()

# Delta vs original
if "Original" in results and len(results) > 1:
    orig_m = results["Original"]["m25k"]["word_acc"]
    orig_h = results["Original"]["maha"]["word_acc"]
    print("  Improvement over original:")
    for name, r in results.items():
        if name == "Original": continue
        dm = r["m25k"]["word_acc"] - orig_m
        dh = r["maha"]["word_acc"] - orig_h
        sign_m = "+" if dm >= 0 else ""
        sign_h = "+" if dh >= 0 else ""
        print(f"    {name:<13}  Marathi25K: {sign_m}{dm:.2f}pp  |  MahaSTR: {sign_h}{dh:.2f}pp")
    print()

# Save results
out = Path("D:/AUS_TEXT/benchmark_compare_results.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write("Model Comparison Benchmark\n")
    f.write(f"{'─'*60}\n")
    for name, r in results.items():
        f.write(f"\n{name}\n")
        f.write(f"  Marathi25K : {r['m25k']['word_acc']:.2f}%  CER={r['m25k']['avg_cer']:.2f}%\n")
        f.write(f"  MahaSTR    : {r['maha']['word_acc']:.2f}%  CER={r['maha']['avg_cer']:.2f}%\n")
print(f"Saved → {out}")
