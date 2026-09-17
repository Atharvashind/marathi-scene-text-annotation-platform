from typing import List, Optional, Sequence
from backend.models import Annotation


def compute_image_metrics(annotations: Sequence[Annotation]) -> dict:
    """
    Compute AAR, BCR, MAR, TSE for a list of non-deleted annotations.
    Returns a dict matching MetricsResponse fields (without image_id).
    """
    active = [a for a in annotations if not a.is_deleted]

    ocr_anns = [a for a in active if a.ocr_generated]
    manual_anns = [a for a in active if not a.ocr_generated]

    total_ocr = len(ocr_anns)
    total_annotations = len(active)

    # AAR: accepted OCR annotations / total OCR annotations
    aar: Optional[float] = None
    if total_ocr > 0:
        accepted_ocr = sum(1 for a in ocr_anns if a.accepted)
        aar = accepted_ocr / total_ocr

    # BCR: corrected OCR annotations / total OCR annotations
    bcr: Optional[float] = None
    if total_ocr > 0:
        corrected_ocr = sum(1 for a in ocr_anns if a.is_corrected)
        bcr = corrected_ocr / total_ocr

    # MAR: manually added annotations / total final annotations
    mar: Optional[float] = None
    if total_annotations > 0:
        mar = len(manual_anns) / total_annotations

    # TSE: AAR * 579 seconds
    tse: Optional[float] = None
    if aar is not None:
        tse = aar * 579.0

    # Confidence counts
    high_confidence_count = sum(1 for a in active if a.confidence > 0.95)
    low_confidence_count = sum(1 for a in active if a.confidence < 0.80)

    return {
        "aar": aar,
        "bcr": bcr,
        "mar": mar,
        "tse": tse,
        "total_ocr": total_ocr,
        "total_annotations": total_annotations,
        "high_confidence_count": high_confidence_count,
        "low_confidence_count": low_confidence_count,
    }


def compute_project_metrics(
    image_annotation_pairs: List[tuple],  # list of (image_id, annotations)
) -> dict:
    """
    Aggregate metrics across all images.
    image_annotation_pairs: list of (image_id, list[Annotation])
    """
    total_images = len(image_annotation_pairs)
    all_annotations = [a for _, anns in image_annotation_pairs for a in anns if not a.is_deleted]
    total_annotations = len(all_annotations)

    # Average confidence across all non-deleted annotations
    average_confidence: Optional[float] = None
    if all_annotations:
        average_confidence = sum(a.confidence for a in all_annotations) / len(all_annotations)

    # Per-image metrics for aggregation
    image_metrics = [compute_image_metrics(anns) for _, anns in image_annotation_pairs]

    def mean_optional(values: list) -> Optional[float]:
        valid = [v for v in values if v is not None]
        return sum(valid) / len(valid) if valid else None

    return {
        "total_images": total_images,
        "total_annotations": total_annotations,
        "average_confidence": average_confidence,
        "mean_aar": mean_optional([m["aar"] for m in image_metrics]),
        "mean_bcr": mean_optional([m["bcr"] for m in image_metrics]),
        "mean_mar": mean_optional([m["mar"] for m in image_metrics]),
        "mean_tse": mean_optional([m["tse"] for m in image_metrics]),
    }
