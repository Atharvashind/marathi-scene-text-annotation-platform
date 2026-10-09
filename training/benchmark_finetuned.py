"""
benchmark_finetuned.py
Runs the fine-tuned marathi_finetuned.ckpt against the Marathi25K test set
and compares results against the baseline benchmark_results.txt.
"""

import sys, os, csv, time
from pathlib import Path

DATASET_ROOT = Path("D:/AUS_TEXT/Marathi25K")
TEST_IMAGES  = DATASET_ROOT / "Test" / "testimages"
TEST_CSV     = DATASET_ROOT / "Test" / "Testlabels.csv"
INDIC_PATH   = "D:/AUS_TEXT/IndicPhotoOCR"
CKPT         = Path("D:/AUS_TEXT/marathi_finetuned.ckpt")
BASELINE_TXT = Path("D:/AUS_TEXT/benchmark_results.txt")
OUT_TXT      = Path("D:/AUS_TEXT/benchmark_finetuned_results.txt")

sys.path.insert(0, INDIC_PATH)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import warnings; warnings.filterwarnings("ignore")

import torch
print("=" * 60)
print("  Marathi25K Benchmark — Fine-tuned PARseq")
print("=" * 60)
print(f"  Checkpoint : {CKPT.name}  ({CKPT.stat().st_size/1e6:.1f} MB)")
print(f"  Device     : {'CUDA — ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
print()

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# ── Patches ───────────────────────────────────────────────────────────────────
import lightning_fabric.utilities.cloud_io as _ci
_orig = _ci._load
def _p(path, map_location=None, weights_only=True):
    return _orig(path, map_location=map_location, weights_only=False)
_ci._load = _p
torch.serialization.add_safe_globals([getattr])

from transformers import AutoImageProcessor as _AIP
_proc = _AIP.from_pretrained("google/vit-base-patch16-224-in21k", use_fast=False)
_orig_aip = _AIP.from_pretrained
def _cached(m, **kw):
    if "vit-base-patch16-224-in21k" in str(m): return _proc
    return _orig_aip(m, **kw)
_AIP.from_pretrained = _cached

# ── Load fine-tuned model ─────────────────────────────────────────────────────
print("Loading fine-tuned model ...")
from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint
from torchvision import transforms as T
from PIL import Image

# Load architecture from original checkpoint, then load fine-tuned weights
model = load_from_checkpoint(
    str(Path(INDIC_PATH) / "IndicPhotoOCR/recognition/models/marathi.ckpt")
)
# Overlay fine-tuned weights
state = torch.load(str(CKPT), map_location=device, weights_only=False)
model.load_state_dict(state["state_dict"])
model = model.to(device).eval()
print("Model loaded OK")
print()

# ── Transform ─────────────────────────────────────────────────────────────────
hp = model.hparams
transform = T.Compose([
    T.Resize(hp.img_size, T.InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(0.5, 0.5),
])

# ── Load test pairs ───────────────────────────────────────────────────────────
pairs = []
with open(TEST_CSV, encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader); next(reader)   # skip both header rows
    for row in reader:
        if len(row) < 2: continue
        fname    = Path(row[0]).name
        label    = row[1].strip()
        img_path = TEST_IMAGES / fname
        if img_path.exists() and label:
            pairs.append((img_path, label))

print(f"Test samples : {len(pairs)}")
print()

# ── Inference ─────────────────────────────────────────────────────────────────
from jiwer import cer as jiwer_cer

correct = total = 0
total_cer = 0.0
len_buckets: dict = {}
errors = []

print("Running inference ...", flush=True)
t0 = time.time()

model.eval()
with torch.no_grad():
    for i, (img_path, true_label) in enumerate(pairs):
        if i % 500 == 0:
            print(f"  {i:5d}/{len(pairs)}  ({time.time()-t0:.1f}s)", flush=True)
        try:
            img    = Image.open(img_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(device)
            logits = model(tensor)
            probs  = logits.softmax(-1)
            preds, _ = model.tokenizer.decode(probs)
            pred   = model.charset_adapter(preds[0])
        except Exception:
            pred = ""

        ok = (pred.strip() == true_label.strip())
        if ok:
            correct += 1
        elif len(errors) < 30:
            errors.append((true_label, pred))

        try:
            c = jiwer_cer(true_label, pred if pred else " ")
        except Exception:
            c = 1.0
        total_cer += c

        L = len(true_label)
        if L not in len_buckets:
            len_buckets[L] = [0, 0]
        len_buckets[L][1] += 1
        if ok:
            len_buckets[L][0] += 1
        total += 1

elapsed = time.time() - t0

# ── Read baseline ─────────────────────────────────────────────────────────────
baseline_acc = baseline_cer = None
if BASELINE_TXT.exists():
    for line in open(BASELINE_TXT, encoding="utf-8"):
        if line.startswith("Word Acc"):
            baseline_acc = float(line.split(":")[1].strip().rstrip("%"))
        if line.startswith("Avg CER"):
            baseline_cer = float(line.split(":")[1].strip().rstrip("%"))

# ── Results ───────────────────────────────────────────────────────────────────
word_acc = correct / total * 100
avg_cer  = total_cer / total * 100

print()
print("=" * 60)
print("  RESULTS")
print("=" * 60)
print(f"  Samples tested   : {total}")
print(f"  Word Accuracy    : {word_acc:.2f}%  ({correct}/{total} correct)")
print(f"  Avg CER          : {avg_cer:.2f}%")
print(f"  Time             : {elapsed:.1f}s  ({elapsed/total*1000:.1f} ms/sample)")
print()

if baseline_acc is not None:
    delta_acc = word_acc - baseline_acc
    delta_cer = avg_cer  - baseline_cer
    print("  Comparison vs baseline (marathi.ckpt):")
    sign_acc = "+" if delta_acc >= 0 else ""
    sign_cer = "+" if delta_cer >= 0 else ""
    print(f"    Word Accuracy : {baseline_acc:.2f}%  →  {word_acc:.2f}%   ({sign_acc}{delta_acc:.2f}pp)")
    print(f"    Avg CER       : {baseline_cer:.2f}%  →  {avg_cer:.2f}%    ({sign_cer}{delta_cer:.2f}pp)")
    if delta_acc > 0:
        print(f"\n  ✓ Fine-tuning IMPROVED accuracy by {delta_acc:.2f} percentage points!")
    elif delta_acc < 0:
        print(f"\n  ✗ Fine-tuning slightly hurt accuracy by {abs(delta_acc):.2f}pp (may need more epochs)")
    else:
        print("\n  — No change in accuracy.")
    print()

print("  Per word-length accuracy:")
for L in sorted(len_buckets):
    c, n = len_buckets[L]
    print(f"    len={L:2d}  {c:5d}/{n:5d}  {c/n*100:6.1f}%")

print()
print("  Errors (fine-tuned model):")
for true, pred in errors[:20]:
    print(f"    {true!r:30s} → {pred!r}")

# ── Save ──────────────────────────────────────────────────────────────────────
with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write(f"Marathi25K Fine-tuned Benchmark\n")
    f.write(f"Checkpoint : {CKPT.name}\n")
    f.write(f"Samples    : {total}\n")
    f.write(f"Word Acc   : {word_acc:.2f}%\n")
    f.write(f"Avg CER    : {avg_cer:.2f}%\n")
    f.write(f"Time       : {elapsed:.1f}s\n")
    if baseline_acc:
        f.write(f"\nBaseline Word Acc : {baseline_acc:.2f}%\n")
        f.write(f"Delta             : {word_acc-baseline_acc:+.2f}pp\n")
    f.write("\nPer-length:\n")
    for L in sorted(len_buckets):
        c, n = len_buckets[L]
        f.write(f"  len={L}  {c}/{n}  {c/n*100:.1f}%\n")
    f.write("\nErrors:\n")
    for true, pred in errors:
        f.write(f"  {true!r} -> {pred!r}\n")

print(f"\nSaved to : {OUT_TXT}")
