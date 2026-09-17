# Marathi OCR Research and Annotation Project

This workspace combines a Marathi OCR research pipeline with the upstream annotation platform repository from GitHub: https://github.com/Atharvashind/marathi-scene-text-annotation-platform.

It includes:

- the OCR research/training workflow for Marathi scene text recognition
- the local benchmarking and fine-tuning scripts
- the annotation platform code under [marathi-scene-text-annotation-platform/](marathi-scene-text-annotation-platform/)
- the project screenshots and benchmark observations used for documentation

## Project overview

The workflow is organized around three connected pieces:

- IndicPhotoOCR for detection, script identification, and recognition
- Marathi25K for training and evaluation data
- the annotation platform for OCR-assisted review and labeling

The annotation platform itself is the upstream GitHub project, already included in this workspace as a local subdirectory and documented in [marathi-scene-text-annotation-platform/README.md](marathi-scene-text-annotation-platform/README.md).

---

## What changed in this project

The main additions here are:

1. a fine-tuning workflow for Marathi word recognition using `finetune.py`
2. benchmark scripts for baseline and fine-tuned evaluation
3. benchmark result files that compare model quality before and after fine-tuning
4. local documentation and screenshots showing the platform usage and OCR output

### Benchmark results

The workspace includes benchmark outputs showing a measurable gain after fine-tuning:

- Baseline model accuracy: 90.94%
- Fine-tuned model accuracy: 94.96%
- Improvement: +4.02 percentage points
- CER reduction: 2.83% → 1.44%

These values are recorded in [benchmark_results.txt](benchmark_results.txt) and [benchmark_finetuned_results.txt](benchmark_finetuned_results.txt).

---

## Repository structure

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

## Annotation platform screenshots

### Screenshot 1

![Marathi OCR annotation workflow](./Screenshot%202026-09-10%20131610.png)

### Screenshot 2

![Marathi OCR detection and review view](./Screenshot%202026-09-10%20131657.png)

---

## How to use this workspace

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

See the local project docs in [marathi-scene-text-annotation-platform/README.md](marathi-scene-text-annotation-platform/README.md).

---

## Upstream project reference

This workspace includes the upstream GitHub repository as the annotation-facing layer for the Marathi OCR pipeline:

- GitHub: https://github.com/Atharvashind/marathi-scene-text-annotation-platform
- Local copy: [marathi-scene-text-annotation-platform/](marathi-scene-text-annotation-platform/)

It complements the research and benchmarking work in this folder by providing the human-in-the-loop labeling workflow, export support, and annotation-review tooling.
- Change label category: `Marathi`, `English`, `Numeric`, `Mixed`, `Logo`
- Toggle accepted/rejected status
- Confidence score displayed to 2 decimal places
- Filter annotations by confidence tier (All / High / Medium / Low)
- All edits persist to database immediately

### Human-in-the-Loop Workflow
Image states progress as: `Uploaded → OCR_Completed → Under_Review → Approved`
- Auto-transition: opening an `OCR_Completed` image sets it to `Under_Review`
- Annotator clicks **Approve** when done
- Approved images lock all annotation edits
- Re-open button reverts to `Under_Review` to enable editing again
- All state changes broadcast via SSE to update gallery badges in real time

### Export
Four export formats, per-image or full project:

| Format | Description |
|---|---|
| **YOLO** | `class_id x_center y_center width height` (normalised) |
| **COCO** | Full JSON schema with `images`, `annotations`, `categories` |
| **Label Studio JSON** | `RectangleLabels` task format |
| **Custom JSON** | All annotation fields for round-trip fidelity |

Export supports optional `status=Approved` filter to export only reviewed images.

### Statistics Dashboard
Per-image stats:
- Total OCR detections
- High confidence count (>0.95)
- Low confidence count (<0.80)
- Annotation Acceptance Rate (AAR)

Project-level stats:
- Total images and annotations
- Average confidence across all annotations
- Mean AAR, BCR, MAR, TSE across all images

---

## API Reference

### Images
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/images/upload` | Upload one or more images |
| `GET` | `/api/images` | List all images |
| `GET` | `/api/images/pending-ocr` | List images with status `Uploaded` |
| `GET` | `/api/images/{id}` | Get image metadata |
| `GET` | `/api/images/{id}/file` | Serve image file |
| `GET` | `/api/images/{id}/thumbnail` | Serve thumbnail |
| `PATCH` | `/api/images/{id}/status` | Update workflow status |
| `DELETE` | `/api/images/{id}` | Delete image + annotations + file |

### OCR
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ocr/{image_id}` | Run OCR on single image |
| `POST` | `/api/ocr/batch/all` | Queue OCR for all `Uploaded` images |

### Annotations
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/annotations/{image_id}` | List annotations for image |
| `POST` | `/api/annotations/{image_id}` | Create manual annotation |
| `PATCH` | `/api/annotations/{annotation_id}` | Update text, label, accepted, or bbox coords |
| `DELETE` | `/api/annotations/{annotation_id}` | Soft-delete annotation |

### Metrics
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/metrics/{image_id}` | Per-image metrics |
| `GET` | `/api/metrics/project` | Project-level aggregate metrics |

### Export
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/export/{image_id}?format=` | Export single image |
| `GET` | `/api/export/project/all?format=&status=` | Export full project |

### Events (SSE)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/events` | Server-Sent Events stream |

SSE event types: `status_changed`, `ocr_completed`, `image_approved`, `batch_ocr_started`, `batch_ocr_progress`, `batch_ocr_image_failed`, `batch_ocr_finished`

---

## Database Schema

```sql
-- Images table
CREATE TABLE images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    filepath    TEXT NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Uploaded',
    upload_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME
);

-- Annotations table
CREATE TABLE annotations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id      INTEGER NOT NULL REFERENCES images(id),
    x1            REAL NOT NULL,
    y1            REAL NOT NULL,
    x2            REAL NOT NULL,
    y2            REAL NOT NULL,
    text          TEXT NOT NULL DEFAULT '',
    label         TEXT NOT NULL DEFAULT 'Marathi',
    confidence    REAL NOT NULL DEFAULT 1.0,
    accepted      BOOLEAN NOT NULL DEFAULT 0,
    ocr_generated BOOLEAN NOT NULL DEFAULT 0,  -- OCR vs manual origin
    is_corrected  BOOLEAN NOT NULL DEFAULT 0,  -- was text/label edited post-OCR
    is_deleted    BOOLEAN NOT NULL DEFAULT 0,  -- soft delete
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Key flags:**
- `ocr_generated` — distinguishes OCR-produced boxes from manually drawn ones (required for AAR/BCR/MAR)
- `is_corrected` — set when text or label is edited on an OCR annotation (drives BCR)
- `is_deleted` — soft delete; annotations are never hard-deleted (audit trail)

---

## Research Metrics

The platform automatically computes four metrics per image and as project aggregates:

| Metric | Formula | Meaning |
|---|---|---|
| **AAR** (Annotation Acceptance Rate) | `accepted OCR boxes / total OCR boxes` | What fraction of OCR output was usable |
| **BCR** (Box Correction Rate) | `corrected OCR boxes / total OCR boxes` | How often annotators had to fix OCR text/labels |
| **MAR** (Manual Addition Rate) | `manually added boxes / total final boxes` | How much was missed by OCR |
| **TSE** (Time Saving Estimate) | `AAR × 579 seconds` | Estimated seconds saved vs fully manual annotation |

The baseline of 579 sec/image is the manual annotation time for Marathi scene text from literature.

All metrics are `null` when the denominator is zero (e.g. no OCR was run).

---

## Known Limitations

### OCR Engine Limitations
1. **Stylized/decorative fonts** — IndicPhotoOCR's TextBPN++ detector is trained on real-world scene text (signboards, street signs). It struggles with artistic fonts, WhatsApp forwards, and political posters with gradient text.
2. **Portrait phone screenshots** — Phone UI chrome (status bar, navigation bar) can confuse the detector.
3. **Very small images** — Images smaller than ~200px in either dimension often yield few or no detections.
4. **No online learning** — Corrections made by annotators do NOT feed back into the OCR model. The model weights are fixed. Corrections are stored for offline fine-tuning only.

### Architecture Limitations
5. **Single user** — No authentication or multi-user support. Anyone with access to `localhost:3000` can modify all annotations.
6. **Local storage only** — Images are stored on the server's local filesystem. No cloud storage integration.
7. **SQLite concurrency** — SQLite handles light concurrent reads fine but will bottleneck under heavy simultaneous writes (e.g. batch OCR + active annotation). Migrate to PostgreSQL for multi-user production use.
8. **No undo** — Deleting an annotation or image is permanent (soft-delete for annotations, hard-delete for images).

---

## Planned Improvements

### OCR Quality
- [ ] **EasyOCR fallback** — automatically retry with EasyOCR when IndicPhotoOCR returns fewer than N detections. EasyOCR handles stylized fonts and artistic text better.
- [ ] **Image pre-processing** — apply CLAHE contrast enhancement and optional sharpening before detection to improve results on low-contrast or blurry images.
- [ ] **Fine-tuning pipeline** — export approved annotations in IndicPhotoOCR training format so the model can be retrained on domain-specific Marathi text.

### Annotation UX
- [ ] **Keyboard shortcuts** — `A` for draw mode, `S` for select, `Escape` to deselect, `Ctrl+Z` undo
- [ ] **Multi-select** — Shift+click to select multiple boxes, then bulk-delete or bulk-label-change
- [ ] **Undo/redo stack** — revert accidental deletions or moves
- [ ] **Mini-map** — overview of full image when zoomed in
- [ ] **Cross-highlight** — hovering an annotation in the panel highlights the corresponding canvas box

### Workflow
- [ ] **User authentication** — login/logout, per-annotator assignment
- [ ] **Multi-annotator support** — assign images to specific annotators, track who approved what
- [ ] **Active Learning integration** — prioritize images where OCR confidence is lowest for human review
- [ ] **Quality scoring** — flag annotations that might be wrong based on confidence patterns

### Infrastructure
- [ ] **PostgreSQL support** — replace SQLite with PostgreSQL for multi-user production
- [ ] **Cloud image storage** — S3/GCS/Azure Blob instead of local filesystem
- [ ] **Docker Compose** — containerize frontend + backend + database for one-command deployment

---

## Deployment Guide

### Current Status: Local development only

The platform currently runs as two local processes (backend + frontend) and is **not production-ready** as-is due to:
- No authentication (anyone on the network can access it)
- Local file storage (not shareable across machines)
- SQLite (not suitable for concurrent users)
- CORS set to `localhost:3000` only

### Steps to make it production-ready

**Step 1 — Add authentication**
Use FastAPI's OAuth2 with JWT tokens or integrate with an identity provider (Auth0, Keycloak).

**Step 2 — Switch to PostgreSQL**
Change `DATABASE_URL` in `backend/config.py`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
```
Add `asyncpg` to `requirements.txt`.

**Step 3 — Use cloud image storage**
Replace `IMAGES_DIR` local writes with S3/GCS upload calls. Return signed URLs for image serving.

**Step 4 — Set CORS to your domain**
In `backend/main.py`, change:
```python
allow_origins=["https://your-domain.com"]
```

**Step 5 — Deploy with Docker**

Example `docker-compose.yml` structure:
```yaml
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://...
      - IMAGES_DIR=/app/images
      - PYTHONPATH=/app/IndicPhotoOCR
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    environment:
      - NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.com
    ports:
      - "3000:3000"
```

**Step 6 — GPU for OCR**
IndicPhotoOCR runs on CPU but is significantly faster on GPU. On a CUDA-capable server, set `ACTIVE_OCR_ENGINE=indic_photo_ocr` and the adapter will auto-detect `cuda:0`.

### Minimum server requirements (CPU-only)
- 4 CPU cores
- 8 GB RAM (IndicPhotoOCR models load ~2–3 GB)
- 50 GB disk (for images and model weights)
- Python 3.9+ (required by IndicPhotoOCR)
- Node.js 18+

---

## Quick Start (Local)

### Prerequisites
- Python 3.9–3.11
- Node.js 18+
- IndicPhotoOCR cloned separately (see below)

### 1. Install IndicPhotoOCR

```bash
git clone https://github.com/Bhashini-IITJ/IndicPhotoOCR.git
# Windows:
$env:PYTHONPATH = "C:\path\to\IndicPhotoOCR"
# Linux/Mac:
export PYTHONPATH=/path/to/IndicPhotoOCR

# Install its dependencies
pip install pytorch-lightning==2.4.0 timm==1.0.11 torchmetrics==1.5.1 \
    shapely==2.0.6 openai-clip==1.0.1 lmdb==1.5.1 easydict==1.13 \
    scipy==1.13.1 datasets==3.1.0 transformers torch torchvision \
    opencv-python jiwer nltk
```

### 2. Start the backend

```bash
# Windows
$env:PYTHONPATH = "C:\path\to\IndicPhotoOCR"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Linux/Mac
PYTHONPATH=/path/to/IndicPhotoOCR uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

### Environment variables (backend)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./annotations.db` | Database connection string |
| `IMAGES_DIR` | `backend/images/` | Where uploaded images are stored |
| `MAX_FILE_SIZE_MB` | `20` | Maximum upload size per file |
| `ACTIVE_OCR_ENGINE` | `indic_photo_ocr` | OCR engine selection |
| `OCR_BATCH_SIZE` | `8` | Batch size for IndicPhotoOCR inference |
| `PYTHONPATH` | — | **Must include path to IndicPhotoOCR repo root** |

### Environment variables (frontend)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL |

---

## Repository

**GitHub:** https://github.com/Atharvashind/marathi-scene-text-annotation-platform

**Spec documents** (requirements, design, tasks): `.kiro/specs/marathi-scene-text-annotation-platform/`
>>>>>>> origin/master
