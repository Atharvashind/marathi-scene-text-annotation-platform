# Implementation Plan: Marathi Scene Text Annotation Platform

## Overview

Implement a full-stack Human-in-the-Loop OCR annotation platform using FastAPI (Python) for the backend and Next.js + TypeScript + TailwindCSS for the frontend. The backend is built in layers — database models → services → routers — and the frontend follows a gallery → canvas editor → annotation panel layout. Each task builds incrementally on prior ones, finishing with full integration and wiring.

## Tasks

- [ ] 1. Set up project structure and shared configuration
  - Initialise the `backend/` directory with a FastAPI app skeleton (`main.py`, `config.py`, `database.py`)
  - Initialise the `frontend/` directory with `create-next-app` using TypeScript and TailwindCSS
  - Add `pyproject.toml` / `requirements.txt` with pinned dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `aiosqlite`, `python-magic`, `hypothesis`, `pytest`, `pytest-asyncio`, `httpx`
  - Add `package.json` with pinned dependencies: `react-konva`, `konva`, `@tanstack/react-query`, `zustand`, `vitest`, `@testing-library/react`
  - Create `config.py` with `IMAGES_DIR`, `DATABASE_URL`, `MAX_FILE_SIZE_MB`, and `ACTIVE_OCR_ENGINE` settings
  - _Requirements: 12.1, 12.3_

- [ ] 2. Implement database models and migrations
  - [ ] 2.1 Define SQLAlchemy 2.0 async ORM models for `Image` and `Annotation` in `backend/models.py`
    - Include all columns from the schema: `images` table (`id`, `filename`, `filepath`, `width`, `height`, `status`, `upload_date`, `approved_at`) and `annotations` table with all flags
    - Add `create_all` startup logic in `database.py` using `AsyncEngine`
    - _Requirements: 1.3, 2.2, 10.1_
  - [ ]* 2.2 Write property test for annotation field persistence (Property 9)
    - **Property 9: Annotation field updates are persisted and retrievable**
    - **Validates: Requirements 4.2, 4.3**

- [ ] 3. Implement Pydantic schemas and shared types
  - Create `backend/schemas.py` with `AnnotationCreate`, `AnnotationUpdate`, `AnnotationResponse`, `ImageResponse`, `MetricsResponse`, `ProjectMetricsResponse`
  - Add `Literal` validator for `label` field restricting to `Marathi`, `English`, `Numeric`, `Mixed`, `Logo`
  - Define TypeScript interfaces in `frontend/src/types/index.ts` mirroring the backend schemas
  - _Requirements: 4.3, 9.4, 12.2_

- [ ] 4. Implement image upload service and router
  - [ ] 4.1 Implement `ImageService` in `backend/services/image_service.py`
    - MIME-type validation using `python-magic` (accept `image/jpeg`, `image/png`, `image/webp`)
    - File size enforcement using `MAX_FILE_SIZE_MB`
    - Save file to `IMAGES_DIR`, read image dimensions, insert `Image` row with `status=Uploaded`
    - Per-file error isolation so a single failure does not abort the batch
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [ ] 4.2 Create `POST /api/images/upload` and `GET /api/images` routes in `backend/routers/images.py`
    - `POST /api/images/upload` accepts `multipart/form-data`, returns per-file result list
    - `GET /api/images` returns all image records with current status
    - `GET /api/images/{image_id}` returns single image metadata
    - `PATCH /api/images/{image_id}/status` enforces the allowed state machine; returns HTTP 409 for invalid transitions
    - _Requirements: 1.5, 6.1, 6.3, 12.1_
  - [ ]* 4.3 Write unit tests for `ImageService.validate_mime_type`
    - Test accepted MIME types (`image/jpeg`, `image/png`, `image/webp`)
    - Test rejected MIME types return descriptive error
    - _Requirements: 1.1, 1.2_

- [ ] 5. Implement OCR adapter layer and OCR service
  - [ ] 5.1 Define `OCRResult` dataclass and `BaseOCRAdapter` abstract class in `backend/ocr/base.py`
    - Interface: `async def run(self, image_path: str) -> Sequence[OCRResult]`
    - _Requirements: 12.2_
  - [ ] 5.2 Implement `IndicPhotoOCRAdapter` in `backend/ocr/indic_photo_ocr.py`
    - Wrap synchronous model inference in `asyncio.get_event_loop().run_in_executor`
    - Use modular pipeline (detect → identify → recognise) with `return_confidence=True`
    - Map library output to `OCRResult` objects
    - _Requirements: 2.1, 12.2, 12.3_
  - [ ] 5.3 Implement `OCRService` in `backend/services/ocr_service.py`
    - Resolve active adapter from config
    - Enforce 60 s timeout with `asyncio.wait_for`; catch `asyncio.TimeoutError` → HTTP 504, catch adapter exceptions → HTTP 502
    - On success: delegate bulk Annotation insertion to `AnnotationService`, set image status to `OCR_Completed`
    - Leave image status unchanged on any failure
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 12.3_
  - [ ] 5.4 Create `POST /api/ocr/{image_id}` route in `backend/routers/ocr.py`
    - _Requirements: 2.1, 2.4, 2.5_
  - [ ]* 5.5 Write property test for OCR failure preserving image status (Property 14)
    - **Property 14: OCR failure preserves image status**
    - **Validates: Requirements 2.5**
  - [ ]* 5.6 Write property test for OCR annotation count (Property 15)
    - **Property 15: OCR annotation count equals OCR detection count**
    - **Validates: Requirements 2.2**

- [ ] 6. Checkpoint — Ensure all backend foundation tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement annotation CRUD service and router
  - [x] 7.1 Implement `AnnotationService` in `backend/services/annotation_service.py`
    - `create`: insert row; for manually drawn boxes set `confidence=1.0`, `accepted=True`, `ocr_generated=False`
    - `update`: if annotation is OCR-generated and `text` or `label` is changed, set `is_corrected=True`; call `MetricsService.recompute` after every mutation
    - `delete`: soft-delete by setting `is_deleted=True`; call `MetricsService.recompute`
    - Guard all mutations: reject with HTTP 403 if parent image has `status=Approved`
    - Persist all changes within the 2-second requirement by using async DB writes
    - _Requirements: 3.6, 4.4, 6.4, 10.1, 10.3_
  - [x] 7.2 Create annotation routes in `backend/routers/annotations.py`
    - `GET /api/annotations/{image_id}` — returns all non-deleted annotations
    - `POST /api/annotations/{image_id}` — creates manual annotation
    - `PATCH /api/annotations/{annotation_id}` — updates text / label / accepted
    - `DELETE /api/annotations/{annotation_id}` — soft-deletes annotation
    - _Requirements: 3.5, 4.2, 4.3, 10.1, 12.1_
  - [ ]* 7.3 Write property test for manual annotation defaults (Property 7)
    - **Property 7: Manual annotations always have confidence 1.0 and accepted true**
    - **Validates: Requirements 3.6**
  - [ ]* 7.4 Write property test for OCR correction sets is_corrected flag (Property 8)
    - **Property 8: OCR annotation modification sets is_corrected**
    - **Validates: Requirements 4.4**
  - [ ]* 7.5 Write property test for approved image blocking mutations (Property 12)
    - **Property 12: Approved image modifications are rejected**
    - **Validates: Requirements 6.4**

- [x] 8. Implement metrics service and router
  - [x] 8.1 Implement `MetricsService` in `backend/services/metrics_service.py`
    - Pure computation functions operating on in-memory annotation lists
    - `compute_image_metrics(annotations)` → AAR, BCR, MAR, TSE (null when respective denominator is 0)
    - `compute_project_metrics(all_images_annotations)` → aggregate mean values, total counts, average confidence
    - TSE formula: `TSE = AAR × 579`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 8.2 Create metrics routes in `backend/routers/metrics.py`
    - `GET /api/metrics/{image_id}` — per-image metrics
    - `GET /api/metrics/project` — project-level aggregates; must return within 5 s for up to 1 000 images
    - _Requirements: 7.2, 7.3, 8.5, 12.1_
  - [ ]* 8.3 Write property test for research metrics formula correctness (Property 3)
    - **Property 3: Research metrics formula correctness (AAR, BCR, MAR)**
    - **Validates: Requirements 8.1, 8.2, 8.3**
  - [ ]* 8.4 Write property test for TSE derivation from AAR (Property 4)
    - **Property 4: TSE is derived from AAR**
    - **Validates: Requirements 8.4**
  - [ ]* 8.5 Write property test for statistics consistency after mutation (Property 13)
    - **Property 13: Statistics are consistent after any annotation mutation**
    - **Validates: Requirements 7.4, 8.6**

- [x] 9. Implement confidence tier utility and colour-coding
  - [x] 9.1 Implement `get_confidence_tier(confidence: float) -> str` in `backend/utils/confidence.py`
    - Returns `"green"` for `> 0.95`, `"yellow"` for `[0.80, 0.95]`, `"red"` for `< 0.80`
    - _Requirements: 3.7, 5.1_
  - [x] 9.2 Implement equivalent `getConfidenceTier` utility in `frontend/src/utils/confidence.ts`
    - Returns the same tier strings and hex colour codes used by react-konva stroke colour
    - _Requirements: 3.7, 5.1_
  - [ ]* 9.3 Write property test for confidence tier assignment (Property 5)
    - **Property 5: Confidence colour tier assignment is total and consistent**
    - **Validates: Requirements 3.7, 5.1**

- [x] 10. Implement export service and router
  - [x] 10.1 Implement `ExportService` in `backend/services/export_service.py`
    - `to_yolo`: normalise coordinates by image W/H; one line per annotation: `class_id x_center y_center width height`
    - `to_coco`: build full COCO JSON with `images`, `annotations`, `categories` arrays
    - `to_label_studio`: build `RectangleLabels` task structure per Label Studio schema
    - `to_custom_json`: serialise all ORM fields (`id`, `image_id`, `x1`, `y1`, `x2`, `y2`, `text`, `label`, `confidence`, `accepted`)
    - Return empty-but-valid output (with response header `X-Empty-Export: true`) when zero annotations match
    - Apply `status=Approved` filter when specified
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  - [x] 10.2 Create export routes in `backend/routers/export.py`
    - `GET /api/export/{image_id}?format=yolo|coco|labelstudio|custom_json`
    - `GET /api/export/project?format=...&status=Approved`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.1_
  - [ ]* 10.3 Write property test for Custom JSON export round-trip (Property 1)
    - **Property 1: Custom JSON export round-trip**
    - **Validates: Requirements 9.4, 9.7**
  - [ ]* 10.4 Write property test for YOLO coordinate normalisation in bounds (Property 2)
    - **Property 2: YOLO coordinate normalisation is in bounds**
    - **Validates: Requirements 9.1**
  - [ ]* 10.5 Write property test for approved-only export filter (Property 6)
    - **Property 6: Approved-only export contains no unapproved annotations**
    - **Validates: Requirements 9.5**

- [x] 11. Implement SSE endpoint for real-time status updates
  - Implement `GET /api/events` SSE route in `backend/routers/events.py` using FastAPI `StreamingResponse`
  - Push events on: OCR completion (`ocr_completed`), image approval (`image_approved`), status change (`status_changed`)
  - Wire `ImageService` and `OCRService` to emit SSE events after state transitions
  - _Requirements: 1.6, 2.4_

- [ ] 12. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Implement frontend API client and state management
  - Create `frontend/src/lib/api.ts` with typed fetch wrappers for every backend endpoint
  - Configure **React Query** client in `frontend/src/providers/QueryProvider.tsx`
  - Create **Zustand** store in `frontend/src/store/annotationStore.ts` with slices for: `selectedAnnotationId`, `canvasMode` (`draw` | `select`), `confidenceFilter` (`all` | `green` | `yellow` | `red`)
  - _Requirements: 1.5, 4.1, 5.3_

- [ ] 14. Implement the Image Gallery view
  - [ ] 14.1 Create `frontend/src/components/ImageGallery.tsx`
    - Fetch image list with React Query (`GET /api/images`)
    - Render thumbnail, filename, and status badge for each image
    - Subscribe to SSE stream to update status badges in real time without full page reload
    - _Requirements: 1.5, 1.6, 6.5_
  - [ ]* 14.2 Write Vitest unit tests for `ImageGallery`
    - Gallery renders correct status badge for each `Annotation_Status` value
    - _Requirements: 1.5_

- [ ] 15. Implement the Top Toolbar
  - [ ] 15.1 Create `frontend/src/components/TopToolbar.tsx`
    - Render "Upload Images", "Run OCR", "Save", and "Export" buttons
    - Disable "Run OCR", "Save", "Export" when no image is selected; show tooltip explaining the constraint
    - "Upload Images" opens a file dialog accepting `image/jpeg`, `image/png`, `image/webp`
    - _Requirements: 11.1, 11.2, 11.3_
  - [ ]* 15.2 Write Vitest unit tests for `TopToolbar`
    - Assert OCR/Save/Export are disabled when no image selected
    - Assert Upload opens file dialog with correct MIME filter
    - _Requirements: 11.2, 11.3_

- [ ] 16. Implement the Annotation Canvas
  - [ ] 16.1 Create `frontend/src/components/AnnotationCanvas.tsx` using `react-konva`
    - Render `Stage` with two `Layer`s: background `Image` node (native aspect ratio) and annotation shapes layer
    - Render each annotation as a `Rect` with border colour from `getConfidenceTier`
    - **Draw mode**: `mousedown` on empty area starts new `Rect`; `mousemove` tracks size; `mouseup` finalises and calls `onAnnotationCreate`
    - **Select mode**: clicking existing box calls `onAnnotationSelect`; attach `Transformer` for resize handles; `transformend` → `onAnnotationUpdate`; `dragend` → `onAnnotationUpdate`
    - Delete selected box via `Delete` key or panel button → `onAnnotationDelete`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_
  - [ ]* 16.2 Write Vitest unit tests for canvas interactions
    - Test draw, select, move, resize, delete interactions via Konva test utilities
    - Test colour-coding by confidence tier
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.7_
  - [ ]* 16.3 Write property test for annotation restoration (Property 16)
    - **Property 16: Annotation restoration on revisit**
    - **Validates: Requirements 10.4**

- [ ] 17. Implement the Annotation Panel
  - [ ] 17.1 Create `frontend/src/components/AnnotationPanel.tsx`
    - Display `text`, `label` dropdown, `confidence` (two decimal places), `accepted` toggle for selected annotation
    - Show confidence colour indicator using `getConfidenceTier`
    - On text commit: call `PATCH /api/annotations/{id}`, invalidate React Query cache
    - On label change: call `PATCH /api/annotations/{id}`
    - Confidence filter controls: render tier buttons that update Zustand `confidenceFilter`; apply filter to displayed annotation list and canvas
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2, 5.3_
  - [ ]* 17.2 Write Vitest unit tests for `AnnotationPanel`
    - Panel populates fields when annotation is selected
    - Confidence indicator uses correct colour class per tier
    - Confidence filter hides/shows annotations correctly
    - _Requirements: 4.1, 5.1, 5.3_
  - [ ]* 17.3 Write property test for confidence filter correctness (Property 10)
    - **Property 10: Confidence tier filter returns only matching annotations**
    - **Validates: Requirements 5.3**

- [ ] 18. Implement workflow state actions in the editor
  - Wire "Run OCR" toolbar button to `POST /api/ocr/{image_id}`; display result annotations on canvas after response; show descriptive error on failure
  - Wire "Save" button to flush pending changes via `PATCH` calls for modified annotations; display confirmation indicator on success, error message with retry on failure
  - Wire "Approve" action: call `PATCH /api/images/{image_id}/status` with `{status: "Approved"}`; lock annotation panel and canvas after approval
  - Wire re-open logic: call `PATCH /api/images/{image_id}/status` with `{status: "Under_Review"}` to re-enable editing
  - Automatically set image status to `Under_Review` when editor is opened for an `OCR_Completed` image
  - _Requirements: 2.4, 6.2, 6.3, 6.4, 10.2, 10.3_

- [ ] 19. Implement the Statistics Dashboard view
  - Create `frontend/src/pages/stats.tsx` (or a modal/drawer component)
  - Fetch per-image metrics from `GET /api/metrics/{image_id}` and project metrics from `GET /api/metrics/project`
  - Display per-image: total OCR detections, high-confidence count (> 0.95), low-confidence count (< 0.80), AAR
  - Display project-level: total images, total annotations, average confidence, TSE, mean AAR/BCR/MAR
  - _Requirements: 7.1, 7.2, 8.5_

- [ ] 20. Implement integration tests
  - [ ] 20.1 Write pytest integration tests using `httpx.AsyncClient` with a real SQLite test DB and a mocked OCR adapter
    - Upload → OCR → retrieve annotations end-to-end flow
    - Approve workflow: attempt edit on Approved image → expect HTTP 403; re-open → edit → expect 200
    - Export endpoints: full pipeline then export, validate response structure for each format
    - SSE endpoint: connect, trigger OCR run, assert event received within timeout
    - _Requirements: 1.3, 2.1, 6.3, 6.4, 9.1, 9.2, 9.3, 9.4_

- [ ] 21. Wire frontend and backend together and final integration
  - Set `NEXT_PUBLIC_API_BASE_URL` env var; configure Next.js `rewrites` or proxy to route `/api/*` to FastAPI
  - Assemble the three-column layout in `frontend/src/pages/index.tsx`: `ImageGallery` | `AnnotationCanvas` | `AnnotationPanel`, topped by `TopToolbar`
  - Ensure selecting an image in the gallery loads its annotations on the canvas and populates the panel
  - Ensure annotation create/update/delete on canvas calls the API and invalidates React Query caches to keep panel and gallery in sync
  - Ensure export button triggers a file download using the correct format endpoint
  - _Requirements: 1.5, 3.1, 4.1, 10.4, 11.1_

- [ ] 22. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- The backend should be built and tested first (tasks 1–12) before frontend work (tasks 13–21)
- Checkpoints at tasks 6, 12, and 22 validate incremental correctness
- Property tests use Hypothesis and MUST include the tag comment: `# Feature: marathi-scene-text-annotation-platform, Property {N}: {property_text}`
- Each property test MUST run a minimum of 100 iterations (`settings(max_examples=100)`)
- Frontend tests use Vitest + React Testing Library
- The OCR adapter pattern (tasks 5.1–5.2) ensures EasyOCR and PaddleOCR can be added without frontend changes (Requirement 12.2, 12.6)
