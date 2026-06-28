import type {
  ImageRecord,
  Annotation,
  AnnotationCreate,
  AnnotationUpdate,
  UploadFileResult,
  ImageMetrics,
  ProjectMetrics,
  ExportFormat,
} from '@/types';

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ── Images ─────────────────────────────────────────────────────────────────────

export async function fetchImages(): Promise<ImageRecord[]> {
  return request<ImageRecord[]>('/api/images');
}

export async function fetchImage(imageId: number): Promise<ImageRecord> {
  return request<ImageRecord>(`/api/images/${imageId}`);
}

export async function updateImageStatus(
  imageId: number,
  status: ImageRecord['status']
): Promise<ImageRecord> {
  return request<ImageRecord>(`/api/images/${imageId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export async function uploadImages(
  files: File[]
): Promise<UploadFileResult[]> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await fetch(`${API_BASE}/api/images/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(detail);
  }
  return res.json();
}

// ── OCR ────────────────────────────────────────────────────────────────────────

export async function runOCR(imageId: number): Promise<Annotation[]> {
  return request<Annotation[]>(`/api/ocr/${imageId}`, { method: 'POST' });
}

// ── Annotations ────────────────────────────────────────────────────────────────

export async function fetchAnnotations(imageId: number): Promise<Annotation[]> {
  return request<Annotation[]>(`/api/annotations/${imageId}`);
}

export async function createAnnotation(
  imageId: number,
  data: AnnotationCreate
): Promise<Annotation> {
  return request<Annotation>(`/api/annotations/${imageId}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAnnotation(
  annotationId: number,
  data: AnnotationUpdate
): Promise<Annotation> {
  return request<Annotation>(`/api/annotations/${annotationId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteAnnotation(annotationId: number): Promise<void> {
  return request<void>(`/api/annotations/${annotationId}`, {
    method: 'DELETE',
  });
}

// ── Metrics ────────────────────────────────────────────────────────────────────

export async function fetchImageMetrics(
  imageId: number
): Promise<ImageMetrics> {
  return request<ImageMetrics>(`/api/metrics/${imageId}`);
}

export async function fetchProjectMetrics(): Promise<ProjectMetrics> {
  return request<ProjectMetrics>('/api/metrics/project');
}

// ── Export ─────────────────────────────────────────────────────────────────────

export function getExportUrl(
  target: 'project' | number,
  format: ExportFormat,
  statusFilter?: string
): string {
  const base =
    target === 'project'
      ? `/api/export/project?format=${format}`
      : `/api/export/${target}?format=${format}`;
  return statusFilter ? `${base}&status=${statusFilter}` : base;
}

export async function downloadExport(
  target: 'project' | number,
  format: ExportFormat,
  statusFilter?: string
): Promise<void> {
  const url = `${API_BASE}${getExportUrl(target, format, statusFilter)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const ext = format === 'yolo' ? 'txt' : 'json';
  a.download = `export_${target}.${ext}`;
  a.click();
  URL.revokeObjectURL(a.href);
}
