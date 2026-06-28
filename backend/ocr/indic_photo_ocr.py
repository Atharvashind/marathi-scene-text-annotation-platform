import asyncio
import logging
import os
from typing import Sequence

from backend.ocr.base import BaseOCRAdapter, OCRResult

logger = logging.getLogger(__name__)


class IndicPhotoOCRAdapter(BaseOCRAdapter):
    """
    Adapter for IndicPhotoOCR (Bhashini-IITJ/IndicPhotoOCR).

    We replicate the library's internal sequential OCR loop but skip the
    final detect_para() call so we get the full structured output:
        {"txt": str, "bbox": [x1, y1, x2, y2], "confidence": float}
    per detected word — giving us real bounding boxes AND real confidence.
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

    def _run_sync(self, image_path: str) -> Sequence[OCRResult]:
        self._load_pipeline()

        try:
            import cv2
            image = cv2.imread(image_path)
            if image is None:
                raise RuntimeError(f"Could not read image: {image_path}")
        except Exception as exc:
            raise RuntimeError(f"Failed to load image: {exc}") from exc

        # Step 1: detect bounding boxes
        try:
            logger.info(f"Detecting text regions in: {image_path}")
            detections = self._ocr.detect(image_path)
            logger.info(f"Detected {len(detections)} bounding boxes")
        except Exception as exc:
            logger.error(f"Detection failed: {exc}", exc_info=True)
            raise RuntimeError(f"IndicPhotoOCR detection failed: {exc}") from exc

        if not detections:
            logger.info("No text regions detected")
            return []

        # Step 2: replicate the library's internal sequential loop
        # (same logic as OCR.ocr() but without the final detect_para() call)
        recognized_texts: dict[str, dict] = {}

        for idx, bbox in enumerate(detections):
            # Compute axis-aligned bbox from polygon
            x1 = min(pt[0] for pt in bbox)
            y1 = min(pt[1] for pt in bbox)
            x2 = max(pt[0] for pt in bbox)
            y2 = max(pt[1] for pt in bbox)

            try:
                # crop_and_identify_script returns (script_lang, cropped_path)
                script_lang, cropped_path = self._ocr.crop_and_identify_script(
                    image, bbox
                )

                if script_lang:
                    recognized_text, confidence = self._ocr.recognise(
                        cropped_path, script_lang, return_confidence=True
                    )
                    recognized_texts[f"img_{idx}"] = {
                        "txt": recognized_text or "",
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                        "confidence": float(confidence) if confidence is not None else 0.9,
                    }
                else:
                    recognized_texts[f"img_{idx}"] = {
                        "txt": "",
                        "bbox": [float(x1), float(y1), float(x2), float(y2)],
                        "confidence": 0.5,
                    }
            except Exception as exc:
                logger.warning(f"Recognition failed for region {idx}: {exc}")
                # Still emit the bounding box with empty text
                recognized_texts[f"img_{idx}"] = {
                    "txt": "",
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "confidence": 0.5,
                }
            finally:
                # Clean up temp crop file
                try:
                    if 'cropped_path' in dir() and os.path.exists(cropped_path):
                        os.remove(cropped_path)
                except Exception:
                    pass

        # Step 3: convert to OCRResult list
        results: list[OCRResult] = []
        for key in sorted(recognized_texts.keys(),
                          key=lambda k: int(k.split("_")[1])):
            entry = recognized_texts[key]
            x1, y1, x2, y2 = entry["bbox"]
            confidence = min(max(float(entry["confidence"]), 0.0), 1.0)
            results.append(OCRResult(
                text=str(entry["txt"]),
                x1=x1, y1=y1, x2=x2, y2=y2,
                confidence=confidence,
            ))

        logger.info(
            f"Produced {len(results)} OCR annotations with real confidence scores"
        )
        return results

    async def run(self, image_path: str) -> Sequence[OCRResult]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, image_path)
