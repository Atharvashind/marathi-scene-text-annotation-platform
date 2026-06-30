from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass
class OCRResult:
    text: str
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float  # in [0.0, 1.0]
    label: str = "Marathi"  # auto-detected script label


class BaseOCRAdapter(ABC):
    @abstractmethod
    async def run(self, image_path: str) -> Sequence[OCRResult]:
        """Accept a local image path and return detected text regions."""
        ...
