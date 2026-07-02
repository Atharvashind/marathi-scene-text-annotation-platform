# Requirements Document

## Introduction

The Marathi Scene Text Annotation Assistant is a web-based Human-in-the-Loop OCR annotation platform designed to accelerate the creation of Marathi scene text datasets. Annotators upload images, trigger OCR auto-annotation via IndicPhotoOCR (with future support for EasyOCR and PaddleOCR), review and correct bounding boxes and transcriptions, then export annotations in standard research formats. The platform measures annotation efficiency through research metrics such as Annotation Acceptance Rate, Box Correction Rate, Manual Addition Rate, and Time Saving Estimate, enabling quantitative evaluation of OCR-assisted annotation workflows.

**Tech Stack:** Next.js + TypeScript + TailwindCSS (frontend), FastAPI + Python (backend), SQLite (database), local folder storage (images).

---

## Glossary

- **Platform**: The Marathi Scene Text Annotation Assistant web application.
- **Annotator**: A human user who reviews, corrects, and approves annotations.
- **Image**: A scene text photograph uploaded to the Platform for annotation.
- **Annotation**: A bounding box paired with a text transcription, label category, and confidence score associated with a region in an Image.
- **Bounding_Box**: A rectangle defined by coordinates (x1, y1, x2, y2) that encloses a text region in an Image.
- **OCR_Engine**: An integrated optical character recognition engine (IndicPhotoOCR, EasyOCR, or PaddleOCR) that produces Annotations automatically.
- **IndicPhotoOCR**: The primary OCR_Engine integrated at launch.
- **Confidence_Score**: A floating-point value in [0.0, 1.0] produced by the OCR_Engine representing its certainty about a predicted text region.
- **Label**: A category tag assigned to an Annotation. Allowed values: `Marathi`, `English`, `Numeric`, `Mixed`, `Logo`.
- **Annotation_Status**: The workflow state of an Image. Allowed values: `Uploaded`, `OCR_Completed`, `Under_Review`, `Approved`.
- **Canvas**: The interactive browser canvas element on which the Annotator draws and manipulates Bounding_Boxes.
- **Project**: The collection of all Images and Annotations managed within a single Platform instance.
- **AAR**: Annotation Acceptance Rate — the ratio of accepted OCR-generated Annotations to total OCR-generated Annotations for an Image.
- **BCR**: Box Correction Rate — the ratio of modified OCR-generated Annotations to total OCR-generated Annotations for an Image.
- **MAR**: Manual Addition Rate — the ratio of manually added Annotations to total final Annotations for an Image.
- **TSE**: Time Saving Estimate — an estimated time saving derived from AAR and a baseline manual annotation time of 579 seconds per Image.
- **Export**: The act of serializing Annotations from the Platform into a downloadable file in a specified format.
- **COCO**: Common Objects in Context JSON annotation format.
- **YOLO**: You Only Look Once annotation format using normalised bounding box coordinates.
- **Label_Studio_JSON**: The JSON annotation format compatible with the Label Studio annotation tool.

---

## Requirements

### Requirement 1: Image Upload

**User Story:** As an Annotator, I want to upload one or more Images to the Platform, so that I can begin the annotation workflow.

#### Acceptance Criteria

1. WHEN an Annotator submits one or more image files through the upload interface, THE Platform SHALL accept files with MIME types `image/jpeg`, `image/png`, and `image/webp`.
2. WHEN an uploaded file's MIME type is not `image/jpeg`, `image/png`, or `image/webp`, THE Platform SHALL reject the file and display a descriptive error message identifying the unsupported file type.
3. WHEN an Image is successfully uploaded, THE Platform SHALL store the file in the configured local folder and persist a record containing `filename`, `width`, `height`, `status` (set to `Uploaded`), and `upload_date` in the database.
4. WHEN multiple images are submitted in a single upload request, THE Platform SHALL process each image independently and report per-file success or failure without aborting the entire batch on a single failure.
5. THE Platform SHALL display a gallery view listing all uploaded Images, showing a thumbnail, filename, and current Annotation_Status for each Image.
6. WHEN an Image's Annotation_Status changes, THE Platform SHALL reflect the updated status in the gallery view without requiring a full page reload.

---

### Requirement 2: OCR Auto-Annotation

**User Story:** As an Annotator, I want to trigger OCR on an Image with a single action, so that bounding boxes and text are populated automatically.

#### Acceptance Criteria

1. WHEN an Annotator clicks "Run OCR" for an Image whose Annotation_Status is `Uploaded` or `Under_Review`, THE Platform SHALL send the Image to IndicPhotoOCR and await results.
2. WHEN IndicPhotoOCR returns results, THE Platform SHALL persist one Annotation record per detected text region, storing `x1`, `y1`, `x2`, `y2`, `text`, `label` (defaulting to `Marathi`), `confidence`, and `accepted` (defaulting to `false`).
3. WHEN OCR results are persisted, THE Platform SHALL update the Image's Annotation_Status to `OCR_Completed`.
4. WHEN the OCR process completes, THE Platform SHALL render all generated Bounding_Boxes on the Canvas overlaid on the Image without requiring a page reload.
5. IF IndicPhotoOCR returns an error or times out after 60 seconds, THEN THE Platform SHALL display a descriptive error message to the Annotator and leave the Image's Annotation_Status unchanged.
6. WHERE a future OCR_Engine (EasyOCR or PaddleOCR) is configured, THE Platform SHALL invoke that engine using the same interface contract, requiring no changes to the frontend.

---

### Requirement 3: Annotation Canvas — Drawing and Manipulation

**User Story:** As an Annotator, I want to draw, move, resize, and delete Bounding_Boxes on the Canvas, so that I can correct or supplement OCR-generated Annotations.

#### Acceptance Criteria

1. THE Canvas SHALL render the Image at its native aspect ratio within the available display area, scaling Bounding_Boxes proportionally.
2. WHEN an Annotator drags on an empty region of the Canvas, THE Canvas SHALL draw a new rectangular Bounding_Box following the cursor, finalising the box on mouse release.
3. WHEN an Annotator drags a resize handle of an existing Bounding_Box, THE Canvas SHALL resize the Bounding_Box in real time, updating the stored coordinates on release.
4. WHEN an Annotator drags the interior of an existing Bounding_Box, THE Canvas SHALL move the Bounding_Box to the new position, updating the stored coordinates on release.
5. WHEN an Annotator selects a Bounding_Box and presses the Delete key or clicks the delete action, THE Canvas SHALL remove the Bounding_Box from the Canvas and mark the corresponding Annotation as deleted in the database.
6. WHEN a new Bounding_Box is finalised by the Annotator, THE Platform SHALL create a new Annotation record with `confidence` set to `1.0` and `accepted` set to `true`, indicating manual origin.
7. WHEN the Canvas is rendered, THE Platform SHALL colour-code each Bounding_Box border: green for Confidence_Score > 0.95, yellow for Confidence_Score in [0.80, 0.95], and red for Confidence_Score < 0.80.

---

### Requirement 4: Text and Label Editing

**User Story:** As an Annotator, I want to edit the transcribed text and label category of any Annotation, so that I can correct OCR errors and apply the correct category.

#### Acceptance Criteria

1. WHEN an Annotator clicks a Bounding_Box on the Canvas, THE Platform SHALL display the corresponding Annotation's `text`, `label`, `confidence`, and `accepted` fields in the right panel.
2. WHEN an Annotator edits the `text` field in the right panel and commits the change, THE Platform SHALL update the Annotation record in the database with the new text.
3. WHEN an Annotator selects a `label` value from the right panel, THE Platform SHALL update the Annotation record with the selected label, which SHALL be one of: `Marathi`, `English`, `Numeric`, `Mixed`, `Logo`.
4. WHEN an Annotator modifies the `text` or `label` of an OCR-generated Annotation, THE Platform SHALL record that the Annotation has been corrected, enabling BCR calculation.
5. THE Platform SHALL display the Confidence_Score beside each Annotation in the right panel, formatted to two decimal places.

---

### Requirement 5: Confidence-Based Review Display

**User Story:** As an Annotator, I want visual confidence indicators on every Annotation, so that I can prioritise which regions require review.

#### Acceptance Criteria

1. THE Platform SHALL display a confidence indicator beside every Annotation in the right panel using the colour scheme: green for Confidence_Score > 0.95, yellow for Confidence_Score in [0.80, 0.95], red for Confidence_Score < 0.80.
2. THE Platform SHALL display the numeric Confidence_Score value alongside the colour indicator, formatted to two decimal places.
3. WHEN the Annotator filters Annotations by confidence tier, THE Platform SHALL display only Annotations matching the selected tier on both the Canvas and in the right panel.

---

### Requirement 6: Human-in-the-Loop Workflow States

**User Story:** As an Annotator, I want to progress an Image through defined workflow states, so that the review status of each Image is clear to all users.

#### Acceptance Criteria

1. THE Platform SHALL maintain an Annotation_Status for every Image with the allowed values: `Uploaded`, `OCR_Completed`, `Under_Review`, `Approved`.
2. WHEN an Annotator opens an Image for editing, THE Platform SHALL set the Image's Annotation_Status to `Under_Review` if it is currently `OCR_Completed`.
3. WHEN an Annotator clicks "Approve" for an Image, THE Platform SHALL set the Image's Annotation_Status to `Approved` and record the approval timestamp.
4. WHEN an Image's Annotation_Status is `Approved`, THE Platform SHALL prevent further modification of its Annotations unless the Annotator explicitly re-opens the Image for editing.
5. THE Platform SHALL display the current Annotation_Status for each Image in the gallery and in the annotation editor.

---

### Requirement 7: Annotation Statistics Dashboard

**User Story:** As an Annotator or researcher, I want to view annotation statistics at both the image and project level, so that I can monitor annotation progress and quality.

#### Acceptance Criteria

1. THE Platform SHALL compute and display the following per-image statistics: total OCR detections, count of Annotations with Confidence_Score > 0.95, count of Annotations with Confidence_Score < 0.80, and OCR Acceptance Rate (accepted Annotations / total OCR Annotations).
2. THE Platform SHALL compute and display the following project-level statistics: total Images uploaded, total Annotations across all Images, average Confidence_Score across all Annotations, and Time Saving Estimate.
3. WHEN project-level statistics are requested, THE Platform SHALL aggregate statistics across all Images in the Project and return the result within 5 seconds for a Project containing up to 1,000 Images.
4. WHEN an Annotation is created, modified, or deleted, THE Platform SHALL update the relevant per-image and project-level statistics to reflect the change.

---

### Requirement 8: Research Metrics Module

**User Story:** As a researcher, I want the Platform to compute AAR, BCR, MAR, and TSE for each Image and for the Project, so that I can quantify the efficiency gain of OCR-assisted annotation.

#### Acceptance Criteria

1. THE Platform SHALL compute AAR per Image as: `AAR = accepted OCR-generated Annotations / total OCR-generated Annotations`. WHEN no OCR-generated Annotations exist for an Image, THE Platform SHALL report AAR as `null`.
2. THE Platform SHALL compute BCR per Image as: `BCR = modified OCR-generated Annotations / total OCR-generated Annotations`. WHEN no OCR-generated Annotations exist for an Image, THE Platform SHALL report BCR as `null`.
3. THE Platform SHALL compute MAR per Image as: `MAR = manually added Annotations / total final Annotations`. WHEN no Annotations exist for an Image, THE Platform SHALL report MAR as `null`.
4. THE Platform SHALL compute TSE per Image as: `TSE = AAR × 579 seconds`, representing estimated seconds saved compared to fully manual annotation of that Image.
5. THE Platform SHALL expose all four metrics (AAR, BCR, MAR, TSE) per Image and as project-level aggregates (mean values across all Images with non-null metrics) through both the dashboard UI and a dedicated API endpoint.
6. WHEN an Annotation's `accepted` or correction state changes, THE Platform SHALL recompute AAR, BCR, MAR, and TSE for the affected Image and update the aggregated project-level metrics.

---

### Requirement 9: Export Annotations

**User Story:** As a researcher, I want to export Annotations in standard formats, so that I can use the dataset with external machine learning tools and compare against other annotation systems.

#### Acceptance Criteria

1. WHEN an Annotator requests a YOLO-format export for an Image or the Project, THE Platform SHALL produce a text file with one line per Annotation in the format: `class_id x_center y_center width height`, where coordinates are normalised to [0.0, 1.0] by Image width and height.
2. WHEN an Annotator requests a COCO-format export for an Image or the Project, THE Platform SHALL produce a JSON file conforming to the COCO annotation schema with `images`, `annotations`, and `categories` fields.
3. WHEN an Annotator requests a Label Studio JSON export for an Image or the Project, THE Platform SHALL produce a JSON file conforming to the Label Studio import/export schema.
4. WHEN an Annotator requests a Custom JSON export, THE Platform SHALL produce a JSON file containing all Annotation fields: `id`, `image_id`, `x1`, `y1`, `x2`, `y2`, `text`, `label`, `confidence`, `accepted`.
5. WHEN the Annotator exports only `Approved` Images, THE Platform SHALL include only Annotations belonging to Images with Annotation_Status `Approved`.
6. IF an export request covers zero Annotations, THEN THE Platform SHALL return an empty but schema-valid file and notify the Annotator that no Annotations matched the export criteria.
7. THE Exporter SHALL produce output that, when re-imported by the same export format's reference tool, results in Annotations equivalent to the originals (round-trip property for Custom JSON format).

---

### Requirement 10: Annotation Persistence and Save

**User Story:** As an Annotator, I want all changes to be saved reliably, so that I do not lose work between sessions.

#### Acceptance Criteria

1. WHEN an Annotator creates, modifies, or deletes an Annotation, THE Platform SHALL persist the change to the database within 2 seconds.
2. WHEN an Annotator clicks "Save", THE Platform SHALL flush all pending Annotation changes for the current Image to the database and display a confirmation indicator.
3. IF a database write fails, THEN THE Platform SHALL display a descriptive error message and retain the unsaved changes in the UI for retry.
4. WHEN an Annotator returns to a previously visited Image, THE Platform SHALL restore all Annotations from the database and render them on the Canvas.

---

### Requirement 11: Top Toolbar Actions

**User Story:** As an Annotator, I want quick access to primary actions from a persistent toolbar, so that I can navigate the workflow efficiently.

#### Acceptance Criteria

1. THE Platform SHALL display a top toolbar containing the following actions: "Upload Images", "Run OCR", "Save", and "Export".
2. WHEN no Image is selected in the editor, THE Platform SHALL disable the "Run OCR", "Save", and "Export" toolbar actions and display a tooltip explaining that an Image must be selected.
3. WHEN the Annotator clicks "Upload Images" in the toolbar, THE Platform SHALL open a file selection dialog accepting `image/jpeg`, `image/png`, and `image/webp` files.

---

### Requirement 12: API Design and OCR Engine Extensibility

**User Story:** As a developer, I want the backend API to be structured so that additional OCR engines can be added without modifying the frontend, so that the Platform can evolve to support EasyOCR and PaddleOCR.

#### Acceptance Criteria

1. THE Platform SHALL expose a REST API with endpoints covering: image upload, OCR trigger, Annotation CRUD, workflow state transitions, statistics retrieval, and export generation.
2. WHEN a new OCR_Engine is configured, THE Platform SHALL invoke it through a common OCR adapter interface that accepts an image path and returns a list of objects each containing `text`, `bounding_box` (`x1`, `y1`, `x2`, `y2`), and `confidence`.
3. THE Platform SHALL support runtime selection of the active OCR_Engine via a configuration parameter, defaulting to `IndicPhotoOCR`.
4. THE Platform SHALL store Annotations independently of the OCR_Engine that produced them, enabling comparison of results from multiple engines on the same Image.
