"""
benchmark.py  —  Marathi OCR Benchmark
Runs the existing IndicPhotoOCR PARseq model against the Marathi25K test set
and reports Word Accuracy, Character Error Rate (CER), and per-length breakdown.

Usage:
    D:\\AUS_TEXT\\train_env\\Scripts\\python.exe D:\\AUS_TEXT\\benchmark.py
"""

import sys, os, csv, time
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
DATASET_ROOT  = Path("D:/AUS_TEXT/Marathi25K")
TEST_IMAGES   = DATASET_ROOT / "Test" / "testimages"
TEST_CSV      = DATASET_ROOT / "Test" / "Testlabels.csv"
INDIC_PATH    = "D:/AUS_TEXT/IndicPhotoOCR"

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, INDIC_PATH)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

import warnings; warnings.filterwarnings("ignore")

import torch
print("="*60)
print("  Marathi25K Benchmark — IndicPhotoOCR PARseq")
print("="*60)
print(f"  Device : {'CUDA — ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
print()

device = "cuda:0" if torch.cuda.is_available() else "cpu"

# ── Patch torch.load for PyTorch 2.6+ weights_only default ───────────────────
import lightning_fabric.utilities.cloud_io as _cloud_io
_orig_cloud_load = _cloud_io._load
def _patched_load(path_or_url, map_location=None, weights_only=True):
    return _orig_cloud_load(path_or_url, map_location=map_location, weights_only=False)
_cloud_io._load = _patched_load
torch.serialization.add_safe_globals([getattr])

# ── Pre-load VIT processor before shapely to avoid DLL conflict ───────────────
print("Loading OCR engine (first time ~30s)...")
from transformers import AutoImageProcessor
_proc = AutoImageProcessor.from_pretrained("google/vit-base-patch16-224-in21k", use_fast=False)
_orig_fpt = AutoImageProcessor.from_pretrained
def _cached_fpt(m, **kw):
    if "vit-base-patch16-224-in21k" in str(m): return _proc
    return _orig_fpt(m, **kw)
AutoImageProcessor.from_pretrained = _cached_fpt

# ── Load model ────────────────────────────────────────────────────────────────
from IndicPhotoOCR.recognition.parseq_recogniser import PARseqrecogniser, model_info
from PIL import Image
from torchvision import transforms as T

recogniser = PARseqrecogniser()
# Load the marathi model (downloads if missing)
marathi_path = Path(INDIC_PATH) / "IndicPhotoOCR" / "recognition" / model_info["marathi"]["path"]
if not marathi_path.exists():
    print("Downloading marathi.ckpt ...")
    marathi_path.parent.mkdir(parents=True, exist_ok=True)
    import requests
    r = requests.get(model_info["marathi"]["url"], stream=True)
    with open(marathi_path, "wb") as f:
        for chunk in r.iter_content(8192): f.write(chunk)

torch_device = torch.device(device)
model = recogniser.load_model(torch_device, str(marathi_path))
print(f"Loaded model: {marathi_path.name}")

# ── Build transform ───────────────────────────────────────────────────────────
hp = model.hparams
transform = T.Compose([
    T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(0.5, 0.5),
])

# ── Load test labels ──────────────────────────────────────────────────────────
pairs = []   # (image_path, true_label)
with open(TEST_CSV, encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)  # skip "image_path,text_label" header
    next(reader)  # skip "Data_Column,Data_Column" row
    for row in reader:
        if len(row) < 2: continue
        fname    = Path(row[0]).name
        label    = row[1].strip()
        img_path = TEST_IMAGES / fname
        if img_path.exists() and label:
            pairs.append((img_path, label))

print(f"Test samples : {len(pairs)}")
print()

# ── Run inference ─────────────────────────────────────────────────────────────
correct     = 0
total       = 0
total_cer   = 0.0
len_buckets = {}   # label_len → (correct, total)
errors      = []   # (true, pred) for first 20 mistakes

print("Running inference", flush=True)
t0 = time.time()

model.eval()
with torch.no_grad():
    for i, (img_path, true_label) in enumerate(pairs):
        if i % 500 == 0:
            elapsed = time.time() - t0
            print(f"  {i:5d}/{len(pairs)}  ({elapsed:.1f}s elapsed)", flush=True)

        try:
            img = Image.open(img_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(torch_device)
            logits = model(tensor)
            probs = logits.softmax(-1)
            preds, _ = model.tokenizer.decode(probs)
            pred_label = model.charset_adapter(preds[0])
        except Exception as e:
            pred_label = ""

        # Word accuracy
        is_correct = (pred_label.strip() == true_label.strip())
        if is_correct:
            correct += 1
        elif len(errors) < 20:
            errors.append((true_label, pred_label))

        # CER — character-level edit distance / length
        from jiwer import cer as jiwer_cer
        try:
            c = jiwer_cer(true_label, pred_label if pred_label else " ")
        except Exception:
            c = 1.0
        total_cer += c

        # Per-length bucket
        L = len(true_label)
        if L not in len_buckets:
            len_buckets[L] = [0, 0]
        len_buckets[L][1] += 1
        if is_correct:
            len_buckets[L][0] += 1

        total += 1

elapsed = time.time() - t0

# ── Results ───────────────────────────────────────────────────────────────────
word_acc = correct / total * 100
avg_cer  = total_cer / total * 100

print()
print("="*60)
print("  RESULTS")
print("="*60)
print(f"  Samples tested   : {total}")
print(f"  Word Accuracy    : {word_acc:.2f}%  ({correct}/{total} correct)")
print(f"  Avg CER          : {avg_cer:.2f}%")
print(f"  Time             : {elapsed:.1f}s  ({elapsed/total*1000:.1f}ms/sample)")
print()

print("  Per word-length accuracy:")
for L in sorted(len_buckets.keys()):
    c, n = len_buckets[L]
    print(f"    len={L:2d}  {c:5d}/{n:5d}  {c/n*100:6.1f}%")

print()
print("  First 20 errors (true → predicted):")
for true, pred in errors:
    print(f"    {true!r:25s} → {pred!r}")

# Save results to file
out_path = Path("D:/AUS_TEXT/benchmark_results.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"Marathi25K Benchmark Results\n")
    f.write(f"Samples  : {total}\n")
    f.write(f"Word Acc : {word_acc:.2f}%\n")
    f.write(f"Avg CER  : {avg_cer:.2f}%\n")
    f.write(f"Time     : {elapsed:.1f}s\n\n")
    f.write("Per-length:\n")
    for L in sorted(len_buckets.keys()):
        c, n = len_buckets[L]
        f.write(f"  len={L}  {c}/{n}  {c/n*100:.1f}%\n")
    f.write("\nErrors:\n")
    for true, pred in errors[:50]:
        f.write(f"  {true!r} → {pred!r}\n")

print(f"\nResults saved to: {out_path}")
