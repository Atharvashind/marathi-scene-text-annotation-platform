import { getSession, signIn } from 'next-auth/react';
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
  const session = await getSession();
  const accessToken = (session as any)?.accessToken;

  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
    ...init,
  });

  if (res.status === 401) {
    // Token expired — redirect to login
    await signIn();
    throw new Error('Session expired. Please log in again.');
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export async function apiSignup(name: string, email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Images ─────────────────────────────────────────────────────────────────────

export async function fetchImages(projectId: string): Promise<ImageRecord[]> {
  return request<ImageRecord[]>(`/projects/${projectId}/images`);
}

export async function fetchImage(projectId: string, imageId: string): Promise<ImageRecord> {
  return request<ImageRecord>(`/projects/${projectId}/images/${imageId}`);
}

export async function updateImageStatus(
  projectId: string, imageId: string, status: ImageRecord['status']
): Promise<ImageRecord> {
  return request<ImageRecord>(`/projects/${projectId}/images/${imageId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export async function uploadImages(projectId: string, files: File[]): Promise<UploadFileResult[]> {
  const session = await getSession();
  const accessToken = (session as any)?.accessToken;
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const res = await fetch(`${API_BASE}/projects/${projectId}/images/upload`, {
    method: 'POST',
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteImage(projectId: string, imageId: string): Promise<void> {
  return request<void>(`/projects/${projectId}/images/${imageId}`, { method: 'DELETE' });
}

export async function runOCR(projectId: string, imageId: string): Promise<Annotation[]> {
  return request<Annotation[]>(`/projects/${projectId}/ocr/${imageId}`, { method: 'POST' });
}

export async function runBatchOCR(projectId: string): Promise<{ queued: number; message: string }> {
  return request(`/projects/${projectId}/ocr/batch/all`, { method: 'POST' });
}

// ── Annotations ────────────────────────────────────────────────────────────────

export async function fetchAnnotations(projectId: string, imageId: string): Promise<Annotation[]> {
  return request<Annotation[]>(`/projects/${projectId}/annotations/${imageId}`);
}

export async function createAnnotation(
  projectId: string, imageId: string, data: AnnotationCreate
): Promise<Annotation> {
  return request<Annotation>(`/projects/${projectId}/annotations/${imageId}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAnnotation(
  projectId: string, annotationId: string, data: AnnotationUpdate
): Promise<Annotation> {
  return request<Annotation>(`/projects/${projectId}/annotations/ann/${annotationId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteAnnotation(projectId: string, annotationId: string): Promise<void> {
  return request<void>(`/projects/${projectId}/annotations/ann/${annotationId}`, { method: 'DELETE' });
}

// ── Metrics ────────────────────────────────────────────────────────────────────

export async function fetchImageMetrics(projectId: string, imageId: string): Promise<ImageMetrics> {
  return request<ImageMetrics>(`/projects/${projectId}/metrics/${imageId}`);
}

export async function fetchProjectMetrics(projectId: string): Promise<ProjectMetrics> {
  return request<ProjectMetrics>(`/projects/${projectId}/metrics/project`);
}

// ── Projects ───────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description?: string;
  default_language: string;
  image_count: number;
  approved_count: number;
  created_at: string;
  updated_at: string;
}

export async function fetchProjects(): Promise<Project[]> {
  return request<Project[]>('/projects');
}

export async function createProject(data: { name: string; description?: string; default_language?: string }): Promise<Project> {
  return request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateProject(id: string, data: { name?: string; description?: string }): Promise<Project> {
  return request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteProject(id: string): Promise<void> {
  return request<void>(`/projects/${id}`, { method: 'DELETE' });
}

// ── Export ─────────────────────────────────────────────────────────────────────

export async function downloadExport(
  projectId: string, target: 'all' | string, format: ExportFormat, statusFilter?: string
): Promise<void> {
  const session = await getSession();
  const accessToken = (session as any)?.accessToken;
  const path = target === 'all'
    ? `/projects/${projectId}/export/all?format=${format}${statusFilter ? `&status=${statusFilter}` : ''}`
    : `/projects/${projectId}/export/${target}?format=${format}`;
  const res = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `export_${target}.${format === 'yolo' ? 'txt' : 'json'}`;
  a.click();
  URL.revokeObjectURL(a.href);
}
