import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
sys.path.insert(0, 'D:/FP(Annotation)/IndicPhotoOCR')

import cv2
from IndicPhotoOCR.ocr import OCR
import torch

ocr = OCR(verbose=False, device='cpu')

# Use a test image
IMAGE = 'D:/FP(Annotation)/backend/images/04ba53a2-Screenshot_2025-12-25_135457.png'
img = cv2.imread(IMAGE)
h, w = img.shape[:2]
print(f"Image size: {w}x{h}")

detections = ocr.detect(IMAGE)
print(f"Detections: {len(detections)}")

# Print first 3 bbox extents
for i, bbox in enumerate(detections[:3]):
    x1 = min(p[0] for p in bbox)
    y1 = min(p[1] for p in bbox)
    x2 = max(p[0] for p in bbox)
    y2 = max(p[1] for p in bbox)
    print(f"  bbox {i}: ({x1:.0f},{y1:.0f}) -> ({x2:.0f},{y2:.0f})  size={x2-x1:.0f}x{y2-y1:.0f}")
    print(f"    as % of image: x1={x1/w*100:.1f}% y1={y1/h*100:.1f}% x2={x2/w*100:.1f}% y2={y2/h*100:.1f}%")
