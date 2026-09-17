# Marathi OCR Research and Annotation Project

This workspace contains the complete pipeline for building and benchmarking a Marathi scene-text recognition workflow using IndicPhotoOCR, plus a human-in-the-loop annotation platform for creating and reviewing OCR labels.

## Project overview

The project combines three main parts:

- IndicPhotoOCR: the OCR backbone for detection, script identification, and recognition
- A fine-tuning pipeline for Marathi word recognition on the Marathi25K dataset
- A web annotation tool for reviewing OCR predictions, correcting bounding boxes/text, and exporting labels

This workspace also includes the upstream annotation platform repository from GitHub: https://github.com/Atharvashind/marathi-scene-text-annotation-platform, which is present locally under [marathi-scene-text-annotation-platform/README.md](marathi-scene-text-annotation-platform/README.md). It functions as the human-in-the-loop layer for this OCR research workflow.

---

## What changed in this project

The main work added here is a practical Marathi OCR research pipeline and evaluation setup.

### 1. Fine-tuning workflow for Marathi recognition
The repository now includes:

- `finetune.py` to build LMDB datasets for training
- `benchmark.py` to evaluate the base IndicPhotoOCR Marathi model
- `benchmark_finetuned.py` to evaluate the fine-tuned checkpoint against the baseline
- `marathi_finetuned.ckpt` as the trained checkpoint

This was implemented to improve recognition accuracy on Marathi scene-text words using the Marathi25K dataset.

### 2. Benchmarking and comparison pipeline
The project now clearly compares:

- the original IndicPhotoOCR Marathi model
- the fine-tuned Marathi model

The benchmark outputs saved in:

- `benchmark_results.txt`
- `benchmark_finetuned_results.txt`

### 3. Windows-safe compatibility fixes
The training and benchmark scripts include compatibility patches for current Python/PyTorch stacks, including:

- `weights_only=False` handling for PyTorch 2.6+
- cached `AutoImageProcessor.from_pretrained(...)` calls to avoid DLL/initialization conflicts
- safer dataset loading and checkpoint usage for local inference and training

### 4. Annotation platform integration
The project also includes the annotation tool in:

- [marathi-scene-text-annotation-platform/](marathi-scene-text-annotation-platform/)
- GitHub source: https://github.com/Atharvashind/marathi-scene-text-annotation-platform

This platform is designed to:

- upload images
- run OCR automatically
- edit bounding boxes and text
- review accepted/rejected labels
- export annotations to ML-friendly formats
- track research metrics such as AAR, BCR, MAR, and TSE

It follows the human-in-the-loop workflow documented in [marathi-scene-text-annotation-platform/README.md](marathi-scene-text-annotation-platform/README.md), including image workflow states, SSE updates, export formats, and metrics dashboards.

---

## Folder structure

```text
AUS_TEXT/
├── README.md
├── finetune.py
├── benchmark.py
├── benchmark_finetuned.py
├── benchmark_results.txt
├── benchmark_finetuned_results.txt
├── marathi_finetuned.ckpt
├── Marathi25K/
├── marathi25k_lmdb/
├── IndicPhotoOCR/
├── marathi-scene-text-annotation-platform/
├── Screenshot 2026-09-10 131610.png
├── Screenshot 2026-09-10 131657.png
└── train_env/
```

---

## Benchmark results

### Baseline model

From `benchmark_results.txt`:

- Samples: 5000
- Word Accuracy: 90.94%
- Avg CER: 2.83%
- Time: 286.6s

### Fine-tuned model

From `benchmark_finetuned_results.txt`:

- Samples: 5000
- Word Accuracy: 94.96%
- Avg CER: 1.44%
- Time: 216.1s

### Improvement summary

- Accuracy gain: +4.02 percentage points
- CER reduction: from 2.83% to 1.44%
- Runtime improvement: faster inference per sample after fine-tuning

This shows the custom Marathi fine-tuning step materially improved the OCR quality on the Marathi25K test set.

---

## How to run the project

### 1. Fine-tune the model

```bash
D:\AUS_TEXT\train_env\Scripts\python.exe D:\AUS_TEXT\finetune.py
```

### 2. Run the baseline benchmark

```bash
D:\AUS_TEXT\train_env\Scripts\python.exe D:\AUS_TEXT\benchmark.py
```

### 3. Run the fine-tuned benchmark

```bash
D:\AUS_TEXT\train_env\Scripts\python.exe D:\AUS_TEXT\benchmark_finetuned.py
```

### 4. Start the annotation platform

See the project documentation in:

- `marathi-scene-text-annotation-platform/README.md`

---

## Annotation platform screenshots

These screenshots show the OCR-assisted annotation workflow and the generated Marathi recognition overlays on scene-text images.

### Screenshot 1

![Marathi OCR annotation workflow](./Screenshot%202026-09-10%20131610.png)

### Screenshot 2

![Marathi OCR detection and review view](./Screenshot%202026-09-10%20131657.png)

---

## Notes

This project is useful for:

- Marathi OCR research and evaluation
- scene-text dataset creation
- annotation-assisted label generation
- benchmarking model improvements on real word-level text data

The workflow is especially valuable when working with noisy real-world signage and street text, where manual correction and OCR-assisted review are both needed.

---

## Related subprojects

- [IndicPhotoOCR/](IndicPhotoOCR/) — OCR detection and recognition pipeline
- [marathi-scene-text-annotation-platform/](marathi-scene-text-annotation-platform/) — annotation web app with OCR review workflow, based on the upstream GitHub project from Atharvashind
- [Marathi25K/](Marathi25K/) — Marathi scene-text dataset used for training and evaluation

## Upstream repository included

The annotation platform repo is incorporated into this workspace as the interactive labeling and review layer for the OCR pipeline:

- GitHub: https://github.com/Atharvashind/marathi-scene-text-annotation-platform
- Local folder: [marathi-scene-text-annotation-platform/](marathi-scene-text-annotation-platform/)

It is used here to support data preparation, correction workflows, and annotation export for the Marathi OCR research pipeline.
