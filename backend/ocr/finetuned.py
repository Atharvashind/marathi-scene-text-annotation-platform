"""
FinetuneOCRAdapter
==================
Uses IndicPhotoOCR's detector (same as the stock adapter) to find text regions,
then replaces the recogniser with our locally fine-tuned TorchScript model
(marathi_finetuned_trace.pt) for recognition.

The finetuned model is a recogniser-only PARSeq/STRHub checkpoint:
  input  : [1, 3, 32, 128]  – one pre-cropped RGB word image, normalised to [-1, 1]
  output : [1, T, C]         – T time-steps × C class logits (argmax-decoded)

Model path is resolved from (in priority order):
  1. FINETUNED_MODEL_PATH env var / config setting
  2. <workspace>/android_agent_bundle/marathi_finetuned_trace.pt  (default)
  3. <workspace>/android_export/marathi_finetuned_trace.pt        (fallback)
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from backend.ocr.base import BaseOCRAdapter, OCRResult

logger = logging.getLogger(__name__)

# ── Default model paths (relative to workspace root) ──────────────────────────
_WORKSPACE = Path(__file__).resolve().parents[2]  # d:\AUS_TEXT
_DEFAULT_PATHS = [
    _WORKSPACE / "android_agent_bundle" / "marathi_finetuned_trace.pt",
    _WORKSPACE / "android_export" / "marathi_finetuned_trace.pt",
]
_CONTRACT_PATH = _WORKSPACE / "android_agent_bundle" / "model_contract.json"

# ── Token table (loaded once from model_contract.json if present) ──────────────
def _load_contract() -> tuple[list[str], str]:
    """Return (token_table, charset_test) from the model contract JSON."""
    if _CONTRACT_PATH.exists():
        try:
            with _CONTRACT_PATH.open("r", encoding="utf-8") as f:
                c = json.load(f)
            return (
                c["model"]["token_table"],
                c["model"]["charset_test"],
            )
        except Exception as exc:
            logger.warning(f"Could not read model_contract.json: {exc}")
    # Minimal fallback — Devanagari block + digits + ASCII letters
    charset = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        "अआइईउऊऋएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह"
        "ािीुूृेैोौंःँ्"
    )
    tokens = ["[E]"] + list(charset) + ["[B]", "[P]"]
    return tokens, charset


TOKEN_TABLE, CHARSET_TEST = _load_contract()


# ── Decoding helper ────────────────────────────────────────────────────────────
def _decode_logits(logits, token_table: list[str], charset: str) -> str:
    """Greedy CTC/AR decode: argmax → token IDs → text, stop at [E]."""
    import torch
    token_ids = logits[0].argmax(dim=-1).tolist()
    chars = []
    for tid in token_ids:
        if tid < len(token_table):
            tok = token_table[tid]
        else:
            continue
        if tok == "[E]":
            break
        if tok not in {"[B]", "[P]"}:
            chars.append(tok)
    text = "".join(chars)
    # Strip characters not in the target charset
    if charset:
        text = re.sub(f"[^{re.escape(charset)}]", "", text)
    return text


# ── Preprocessing ──────────────────────────────────────────────────────────────
def _preprocess_crop(crop_bgr: np.ndarray) -> "torch.Tensor":
    """BGR crop → [1, 3, 32, 128] float32 tensor in [-1, 1]."""
    import torch
    # Resize to (W=128, H=32) — cv2 takes (width, height)
    resized = cv2.resize(crop_bgr, (128, 32), interpolation=cv2.INTER_CUBIC)
    # BGR → RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    # HWC [0,255] → CHW float32 [−1, 1]
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
    tensor = (tensor - 0.5) / 0.5
    return tensor.unsqueeze(0)  # [1, 3, 32, 128]


# ── Adapter ────────────────────────────────────────────────────────────────────
class FinetuneOCRAdapter(BaseOCRAdapter):
    """
    OCR adapter that combines:
    - IndicPhotoOCR detector  →  bounding boxes
    - Our finetuned TorchScript recogniser  →  text per crop
    """

    def __init__(self, model_path: str | None = None):
        self._model_path: str | None = model_path
        self._model = None       # TorchScript recogniser
        self._detector = None    # IndicPhotoOCR OCR object (detect-only)

    # ── Lazy loaders ──────────────────────────────────────────────────────────
    def _resolve_model_path(self) -> Path:
        # 1. Explicit constructor arg
        if self._model_path:
            p = Path(self._model_path)
            if p.exists():
                return p
            raise RuntimeError(f"Finetuned model not found at: {p}")
        # 2. Env var / config
        env_path = os.environ.get("FINETUNED_MODEL_PATH", "").strip()
        if env_path:
            p = Path(env_path)
            if p.exists():
                return p
            raise RuntimeError(f"FINETUNED_MODEL_PATH={env_path} does not exist")
        # 3. Default locations
        for p in _DEFAULT_PATHS:
            if p.exists():
                return p
        raise RuntimeError(
            "Finetuned model not found. Set FINETUNED_MODEL_PATH or place "
            "marathi_finetuned_trace.pt in android_agent_bundle/ or android_export/."
        )

    def _load_recogniser(self):
        if self._model is not None:
            return
        import torch
        path = self._resolve_model_path()
        logger.info(f"Loading finetuned recogniser from: {path}")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self._model = torch.jit.load(str(path), map_location=device)
        self._model.eval()
        self._device = device
        logger.info(f"Finetuned recogniser loaded on {device}")

    def _load_detector(self):
        if self._detector is not None:
            return
        try:
            from IndicPhotoOCR.ocr import OCR  # type: ignore
            import torch
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading IndicPhotoOCR detector on: {device}")
            # We only use the detector — keep verbose off
            self._detector = OCR(verbose=False, identifier_lang="auto", device=device)
            logger.info("IndicPhotoOCR detector loaded successfully")
        except ImportError as exc:
            raise RuntimeError(
                f"IndicPhotoOCR import failed: {exc}. "
                "Set PYTHONPATH to the IndicPhotoOCR repo root."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"IndicPhotoOCR detector failed to initialise: {exc}") from exc

    # ── Core inference ─────────────────────────────────────────────────────────
    def _run_sync(self, image_path: str) -> Sequence[OCRResult]:
        self._load_recogniser()
        self._load_detector()

        import torch

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"Could not read image: {image_path}")

        # Step 1: Detect text regions using IndicPhotoOCR detector
        try:
            logger.info(f"[Finetuned] Detecting text regions in: {image_path}")
            detections = self._detector.detect(image_path)
            logger.info(f"[Finetuned] Detected {len(detections)} regions")
        except Exception as exc:
            raise RuntimeError(f"Detection failed: {exc}") from exc

        if not detections:
            return []

        results: list[OCRResult] = []

        for bbox in detections:
            # Compute axis-aligned bounding box
            x1 = float(min(pt[0] for pt in bbox))
            y1 = float(min(pt[1] for pt in bbox))
            x2 = float(max(pt[0] for pt in bbox))
            y2 = float(max(pt[1] for pt in bbox))

            # Clamp to image bounds
            h_img, w_img = image.shape[:2]
            ix1, iy1 = max(0, int(x1)), max(0, int(y1))
            ix2, iy2 = min(w_img, int(x2)), min(h_img, int(y2))

            if ix2 <= ix1 or iy2 <= iy1:
                continue

            # Crop and recognise with finetuned model
            try:
                crop = image[iy1:iy2, ix1:ix2]
                tensor = _preprocess_crop(crop).to(self._device)

                with torch.no_grad():
                    logits = self._model(tensor)

                text = _decode_logits(logits, TOKEN_TABLE, CHARSET_TEST)

                # Compute a simple confidence from the softmax entropy
                probs = torch.softmax(logits[0], dim=-1)
                max_probs = probs.max(dim=-1).values
                confidence = float(max_probs.mean().item())
                confidence = min(max(confidence, 0.0), 1.0)

                # All text from our finetuned Marathi model → label Marathi
                # (override to Numeric if purely digits)
                clean = text.replace(" ", "").replace(".", "").replace(",", "")
                label = "Numeric" if clean.isdigit() and clean else "Marathi"

                results.append(OCRResult(
                    text=text,
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=confidence,
                    label=label,
                ))

            except Exception as exc:
                logger.warning(f"[Finetuned] Recognition failed for bbox ({x1},{y1},{x2},{y2}): {exc}")
                results.append(OCRResult(
                    text="", x1=x1, y1=y1, x2=x2, y2=y2,
                    confidence=0.5, label="Marathi",
                ))

        logger.info(f"[Finetuned] Produced {len(results)} annotations")
        return results

    async def run(self, image_path: str) -> Sequence[OCRResult]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, image_path)
