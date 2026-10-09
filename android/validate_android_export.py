import csv
import os
import shutil
import sys
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms as T

ROOT = Path(__file__).resolve().parent
INDIC_PATH = ROOT / "IndicPhotoOCR"
CHECKPOINT = ROOT / "marathi_finetuned.ckpt"
TEST_IMAGES = ROOT / "Marathi25K" / "Test" / "testimages"
TEST_LABELS = ROOT / "Marathi25K" / "Test" / "Testlabels.csv"
BUNDLE = ROOT / "android_agent_bundle"
MODEL_PATH = BUNDLE / "marathi_finetuned_trace.pt"
MIN_LABEL_CODEPOINTS = 6
MAX_SAMPLES = 60
PACKAGED_SAMPLES = 12

sys.path.insert(0, str(INDIC_PATH))
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from IndicPhotoOCR.utils.strhub.models.utils import load_from_checkpoint


def main():
    model = load_from_checkpoint(str(CHECKPOINT), map_location="cpu").eval()
    exported = torch.jit.load(str(MODEL_PATH), map_location="cpu").eval()
    transform = T.Compose(
        [
            T.Resize(model.hparams.img_size, T.InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(0.5, 0.5),
        ]
    )

    candidates = []
    with TEST_LABELS.open(encoding="utf-8-sig", newline="") as labels_file:
        for row in csv.DictReader(labels_file):
            expected = (row.get("text_label") or "").strip()
            if len(expected) < MIN_LABEL_CODEPOINTS:
                continue
            image_path = TEST_IMAGES / Path(row["image_path"]).name
            if expected and image_path.is_file():
                candidates.append((image_path, expected))

    results = []
    for image_path, expected in candidates[:MAX_SAMPLES]:
        image = Image.open(image_path).convert("RGB")
        tensor = transform(image).unsqueeze(0)
        with torch.inference_mode():
            original_logits = model(tensor)
            exported_logits = exported(tensor)
        original_labels, _ = model.tokenizer.decode(original_logits.softmax(-1))
        exported_labels, _ = model.tokenizer.decode(exported_logits.softmax(-1))
        original_text = model.charset_adapter(original_labels[0])
        exported_text = model.charset_adapter(exported_labels[0])
        results.append(
            {
                "image": image_path.name,
                "expected": expected,
                "original_prediction": original_text,
                "torchscript_prediction": exported_text,
                "matches_original": original_text == exported_text,
                "matches_expected": exported_text == expected,
            }
        )

    if len(results) != min(len(candidates), MAX_SAMPLES) or not results:
        raise RuntimeError(f"Expected validation samples, found {len(results)}")
    parity_count = sum(row["matches_original"] for row in results)
    if parity_count != len(results):
        raise RuntimeError(f"Export differs from original on {len(results) - parity_count} samples")

    results_path = BUNDLE / "validation_results.csv"
    with results_path.open("w", encoding="utf-8-sig", newline="") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    samples_dir = BUNDLE / "validation_samples"
    samples_dir.mkdir(exist_ok=True)
    manifest_path = samples_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=["image", "expected", "original_prediction", "torchscript_prediction"])
        writer.writeheader()
        for row in results[:PACKAGED_SAMPLES]:
            shutil.copy2(TEST_IMAGES / row["image"], samples_dir / row["image"])
            writer.writerow({key: row[key] for key in writer.fieldnames})

    expected_count = sum(row["matches_expected"] for row in results)
    print(f"Compared with original: {parity_count}/{len(results)} identical")
    print(f"TorchScript matches labels: {expected_count}/{len(results)}")
    print(f"Full results: {results_path}")
    print(f"Packaged crop samples: {samples_dir}")


if __name__ == "__main__":
    main()