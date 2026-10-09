// Shared types and helpers — no Konva imports, safe to use on server.

export interface Annotation {
  id: string;
  image_id: string;
  x1: number; y1: number; x2: number; y2: number;
  text: string;
  label: string;
  confidence?: number;
  accepted?: boolean;
  created_at: string;
}

export const LABEL_COLORS: Record<string, string> = {
  Marathi: '#10B981',
  English: '#3B82F6',
  Numeric: '#F59E0B',
  Mixed:   '#8B5CF6',
  Logo:    '#EF4444',
};

export function labelColor(label: string): string {
  return LABEL_COLORS[label] ?? '#10B981';
}
