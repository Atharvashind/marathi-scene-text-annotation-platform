import json
from typing import List, Tuple, Optional
from backend.models import Image, Annotation

LABEL_TO_CLASS_ID = {
    "Marathi": 0,
    "English": 1,
    "Numeric": 2,
    "Mixed": 3,
    "Logo": 4,
}


def _active_annotations(annotations: List[Annotation]) -> List[Annotation]:
    return [a for a in annotations if not a.is_deleted]


def to_yolo(image: Image, annotations: List[Annotation]) -> str:
    """
    YOLO format: class_id x_center y_center width height (normalised to [0,1])
    """
    lines = []
    W, H = float(image.width), float(image.height)
    for ann in _active_annotations(annotations):
        class_id = LABEL_TO_CLASS_ID.get(ann.label, 0)
        x_center = ((ann.x1 + ann.x2) / 2) / W
        y_center = ((ann.y1 + ann.y2) / 2) / H
        width = abs(ann.x2 - ann.x1) / W
        height = abs(ann.y2 - ann.y1) / H
        lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    return "\n".join(lines)


def to_coco(
    image_annotation_pairs: List[Tuple[Image, List[Annotation]]]
) -> dict:
    """
    COCO format with images, annotations, and categories arrays.
    """
    categories = [
        {"id": cid, "name": name}
        for name, cid in LABEL_TO_CLASS_ID.items()
    ]

    coco_images = []
    coco_annotations = []
    ann_id = 1

    for image, annotations in image_annotation_pairs:
        coco_images.append({
            "id": image.id,
            "file_name": image.filename,
            "width": image.width,
            "height": image.height,
        })
        for ann in _active_annotations(annotations):
            w = abs(ann.x2 - ann.x1)
            h = abs(ann.y2 - ann.y1)
            coco_annotations.append({
                "id": ann_id,
                "image_id": image.id,
                "category_id": LABEL_TO_CLASS_ID.get(ann.label, 0),
                "bbox": [ann.x1, ann.y1, w, h],   # COCO uses [x, y, w, h]
                "area": w * h,
                "iscrowd": 0,
                "text": ann.text,
                "confidence": ann.confidence,
            })
            ann_id += 1

    return {
        "images": coco_images,
        "annotations": coco_annotations,
        "categories": categories,
    }


def to_label_studio(
    image_annotation_pairs: List[Tuple[Image, List[Annotation]]]
) -> list:
    """
    Label Studio JSON format with RectangleLabels tasks.
    """
    tasks = []
    for image, annotations in image_annotation_pairs:
        results = []
        for ann in _active_annotations(annotations):
            W, H = float(image.width), float(image.height)
            # Label Studio uses percentage coordinates
            results.append({
                "id": str(ann.id),
                "type": "rectanglelabels",
                "from_name": "label",
                "to_name": "image",
                "original_width": image.width,
                "original_height": image.height,
                "image_rotation": 0,
                "value": {
                    "rotation": 0,
                    "x": ann.x1 / W * 100,
                    "y": ann.y1 / H * 100,
                    "width": abs(ann.x2 - ann.x1) / W * 100,
                    "height": abs(ann.y2 - ann.y1) / H * 100,
                    "rectanglelabels": [ann.label],
                },
                "meta": {"text": ann.text, "confidence": ann.confidence},
            })
        tasks.append({
            "data": {"image": image.filename},
            "annotations": [{"result": results}],
        })
    return tasks


def to_custom_json(
    image_annotation_pairs: List[Tuple[Image, List[Annotation]]]
) -> list:
    """
    Custom JSON: all annotation fields serialised verbatim.
    """
    output = []
    for image, annotations in image_annotation_pairs:
        for ann in _active_annotations(annotations):
            output.append({
                "id": ann.id,
                "image_id": ann.image_id,
                "x1": ann.x1,
                "y1": ann.y1,
                "x2": ann.x2,
                "y2": ann.y2,
                "text": ann.text,
                "label": ann.label,
                "confidence": ann.confidence,
                "accepted": ann.accepted,
            })
    return output
