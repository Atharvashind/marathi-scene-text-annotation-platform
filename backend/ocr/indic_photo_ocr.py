import asyncio
import logging
import os
from typing import Sequence

from backend.ocr.base import BaseOCRAdapter, OCRResult

logger = logging.getLogger(__name__)

# Map IndicPhotoOCR script names → platform label categories
SCRIPT_TO_LABEL: dict[str, str] = {
    "hindi": "Marathi",
    "marathi": "Marathi",
    "devanagari": "Marathi",
    "english": "English",
    "eng": "English",
    "latin": "English",
    "numeric": "Numeric",
    "number": "Numeric",
    "mixed": "Mixed",
    "logo": "Logo",
    "bengali": "Marathi",
    "gujarati": "Marathi",
    "punjabi": "Marathi",
    "tamil": "Marathi",
    "telugu": "Marathi",
    "kannada": "Marathi",
    "malayalam": "Marathi",
    "odia": "Marathi",
    "assamese": "Marathi",
}

# Batch size for parallel inference — tunable via env var
BATCH_SIZE = int(os.environ.get("OCR_BATCH_SIZE", "8"))


class IndicPhotoOCRAdapter(BaseOCRAdapter):
    """
    Adapter for IndicPhotoOCR (Bhashini-IITJ/IndicPhotoOCR).

    Uses the library's batch inference pipeline:
      1. detect(image_path)           → polygon bboxes
      2. crop_bbox() per detection    → temp crop files
      3. identify_batch()             → script lang per crop
      4. recognise_batch() per lang   → (text, confidence) per crop

    Batch mode avoids the sequential meta-tensor error and is significantly
    faster. Falls back to sequential mode if batch inference fails.
    """

    def __init__(self):
        self._ocr = None

    def _load_pipeline(self):
        if self._ocr is not None:
            return
        try:
            from IndicPhotoOCR.ocr import OCR  # type: ignore
            import torch
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading IndicPhotoOCR on device: {device}")
            self._ocr = OCR(verbose=False, identifier_lang="auto", device=device)
            logger.info("IndicPhotoOCR loaded successfully")
        except ImportError as exc:
            logger.error(f"ImportError: {exc}")
            raise RuntimeError(
                f"IndicPhotoOCR import failed: {exc}. "
                "Set PYTHONPATH to the IndicPhotoOCR repo root."
            ) from exc
        except Exception as exc:
            logger.error(f"Error loading IndicPhotoOCR: {exc}", exc_info=True)
            raise RuntimeError(f"IndicPhotoOCR failed to initialise: {exc}") from exc

    @staticmethod
    def _infer_label(script_lang: str, text: str) -> str:
        """Determine label from script language and text content."""
        # Purely numeric text overrides script detection
        clean = str(text).replace('.', '').replace(',', '').replace('-', '').replace(' ', '')
        if clean.isdigit() and clean:
            return "Numeric"
        return SCRIPT_TO_LABEL.get(str(script_lang).lower(), "Marathi")

    def _run_sync(self, image_path: str) -> Sequence[OCRResult]:
        self._load_pipeline()

        try:
            import cv2
            image = cv2.imread(image_path)
            if image is None:
                raise RuntimeError(f"Could not read image: {image_path}")
        except Exception as exc:
            raise RuntimeError(f"Failed to load image: {exc}") from exc

        # Step 1: detect
        try:
            logger.info(f"Detecting text regions in: {image_path}")
            detections = self._ocr.detect(image_path)
            logger.info(f"Detected {len(detections)} bounding boxes")
        except Exception as exc:
            logger.error(f"Detection failed: {exc}", exc_info=True)
            raise RuntimeError(f"IndicPhotoOCR detection failed: {exc}") from exc

        if not detections:
            return []

        # Step 2: crop all detections to temp files
        cropped_paths: list[str] = []
        bboxes: list[tuple[float, float, float, float]] = []

        for bbox in detections:
            x1 = min(pt[0] for pt in bbox)
            y1 = min(pt[1] for pt in bbox)
            x2 = max(pt[0] for pt in bbox)
            y2 = max(pt[1] for pt in bbox)
            bboxes.append((float(x1), float(y1), float(x2), float(y2)))
            try:
                crop_path = self._ocr.crop_bbox(image, bbox)
                cropped_paths.append(crop_path)
            except Exception as exc:
                logger.warning(f"Crop failed for bbox {bbox}: {exc}")
                cropped_paths.append("")

        valid_paths = [p for p in cropped_paths if p]
        logger.info(f"Cropped {len(valid_paths)}/{len(detections)} regions successfully")

        results: list[OCRResult] = []

        # Step 3: try batch inference first
        batch_success = False
        if valid_paths and BATCH_SIZE > 0:
            try:
                results = self._run_batch(cropped_paths, bboxes)
                batch_success = True
                logger.info(f"Batch inference succeeded: {len(results)} annotations")
            except Exception as exc:
                logger.warning(f"Batch inference failed ({exc}), falling back to sequential")

        # Step 4: fallback to sequential if batch failed
        if not batch_success:
            results = self._run_sequential(image, detections, bboxes, cropped_paths)
            logger.info(f"Sequential inference: {len(results)} annotations")

        # Cleanup temp crop files
        for p in cropped_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        logger.info(f"Produced {len(results)} OCR annotations")
        return results

    def _run_batch(
        self,
        cropped_paths: list[str],
        bboxes: list[tuple[float, float, float, float]],
    ) -> list[OCRResult]:
        """Batch inference using identify_batch + recognise_batch."""
        valid = [(i, p) for i, p in enumerate(cropped_paths) if p]
        if not valid:
            return []

        indices = [i for i, _ in valid]
        paths = [p for _, p in valid]

        # Identify scripts in batch
        script_langs = self._ocr.identifier.identify_batch(
            paths, "auto", self._ocr.device, batch_size=BATCH_SIZE
        )

        # Group by language for batch recognition
        lang_groups: dict[str, list[tuple[int, str]]] = {}
        for idx, (orig_idx, path) in enumerate(zip(indices, paths)):
            lang = script_langs[idx] if idx < len(script_langs) else "hindi"
            lang_groups.setdefault(lang, []).append((orig_idx, path))

        # recognise_batch per language group
        recognition_map: dict[int, tuple[str, float]] = {}
        for lang, items in lang_groups.items():
            orig_indices = [i for i, _ in items]
            group_paths = [p for _, p in items]
            try:
                batch_results = self._ocr.recogniser.recognise_batch(
                    lang, group_paths, lang,
                    self._ocr.verbose, self._ocr.device,
                    return_confidence=True,
                    batch_size=BATCH_SIZE,
                )
                for orig_idx, (text, conf) in zip(orig_indices, batch_results):
                    recognition_map[orig_idx] = (str(text or ""), float(conf or 0.9))
            except Exception as exc:
                logger.warning(f"Batch recognition failed for lang={lang}: {exc}")
                for orig_idx in orig_indices:
                    recognition_map[orig_idx] = ("", 0.5)

        # Build results preserving original order
        results: list[OCRResult] = []
        for i, (x1, y1, x2, y2) in enumerate(bboxes):
            text, confidence = recognition_map.get(i, ("", 0.5))
            # Get script lang for this index
            try:
                pos_in_valid = indices.index(i)
                script_lang = script_langs[pos_in_valid] if pos_in_valid < len(script_langs) else "hindi"
            except ValueError:
                script_lang = "hindi"
            label = self._infer_label(script_lang, text)
            results.append(OCRResult(
                text=text,
                x1=x1, y1=y1, x2=x2, y2=y2,
                confidence=min(max(confidence, 0.0), 1.0),
                label=label,
            ))
        return results

    def _run_sequential(
        self,
        image,
        detections: list,
        bboxes: list[tuple[float, float, float, float]],
        cropped_paths: list[str],
    ) -> list[OCRResult]:
        """Sequential inference — fallback when batch fails."""
        results: list[OCRResult] = []
        for idx, (bbox, (x1, y1, x2, y2)) in enumerate(zip(detections, bboxes)):
            crop_path = cropped_paths[idx] if idx < len(cropped_paths) else ""
            try:
                if not crop_path:
                    script_lang, crop_path = self._ocr.crop_and_identify_script(image, bbox)
                else:
                    script_lang = self._ocr.identify(crop_path)

                if script_lang and crop_path:
                    try:
                        text, confidence = self._ocr.recognise(
                            crop_path, script_lang, return_confidence=True
                        )
                        confidence = float(confidence) if confidence is not None else 0.9
                    except Exception:
                        text = self._ocr.recognise(crop_path, script_lang)
                        confidence = 0.9
                    label = self._infer_label(script_lang, str(text or ""))
                    results.append(OCRResult(
                        text=str(text or ""),
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        confidence=min(max(confidence, 0.0), 1.0),
                        label=label,
                    ))
                else:
                    results.append(OCRResult(
                        text="", x1=x1, y1=y1, x2=x2, y2=y2,
                        confidence=0.5, label="Marathi",
                    ))
            except Exception as exc:
                logger.warning(f"Sequential recognition failed for region {idx}: {exc}")
                results.append(OCRResult(
                    text="", x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=0.5, label="Marathi",
                ))
        return results

    async def run(self, image_path: str) -> Sequence[OCRResult]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, image_path)
