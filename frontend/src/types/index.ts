// ── Image types ────────────────────────────────────────────────────────────────

export type AnnotationStatus = 'Uploaded' | 'OCR_Completed' | 'Under_Review' | 'Approved';

export interface ImageRecord {
  id: number;
  filename: string;
  filepath: string;
  width: number;
  height: number;
  status: AnnotationStatus;
  upload_date: string;
  approved_at: string | null;
}

// ── Annotation types ───────────────────────────────────────────────────────────

export type LabelType = 'Marathi' | 'English' | 'Numeric' | 'Mixed' | 'Logo';

export interface Annotation {
  id: number;
  image_id: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  text: string;
  label: LabelType;
  confidence: number;
  accepted: boolean;
  ocr_generated: boolean;
  is_corrected: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnnotationCreate {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  text?: string;
  label?: LabelType;
}

export interface AnnotationUpdate {
  text?: string;
  label?: LabelType;
  accepted?: boolean;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
}

// ── Upload types ───────────────────────────────────────────────────────────────

export interface UploadFileResult {
  filename: string;
  success: boolean;
  image?: ImageRecord;
  error?: string;
}

// ── Metrics types ──────────────────────────────────────────────────────────────

export interface ImageMetrics {
  image_id: number;
  aar: number | null;
  bcr: number | null;
  mar: number | null;
  tse: number | null;
  total_ocr: number;
  total_annotations: number;
  high_confidence_count: number;
  low_confidence_count: number;
}

export interface ProjectMetrics {
  total_images: number;
  total_annotations: number;
  average_confidence: number | null;
  mean_aar: number | null;
  mean_bcr: number | null;
  mean_mar: number | null;
  mean_tse: number | null;
}

// ── Export types ───────────────────────────────────────────────────────────────

export type ExportFormat = 'yolo' | 'coco' | 'labelstudio' | 'custom_json';

// ── Canvas / UI types ──────────────────────────────────────────────────────────

export type CanvasMode = 'draw' | 'select';
export type ConfidenceTier = 'all' | 'green' | 'yellow' | 'red';
