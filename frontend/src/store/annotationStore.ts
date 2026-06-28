import { create } from 'zustand';
import type { CanvasMode } from '@/types';

type ConfidenceFilter = 'all' | 'green' | 'yellow' | 'red';

interface AnnotationStore {
  // Selected image
  selectedImageId: number | null;
  setSelectedImageId: (id: number | null) => void;

  // Selected annotation
  selectedAnnotationId: number | null;
  setSelectedAnnotationId: (id: number | null) => void;

  // Canvas interaction mode
  canvasMode: CanvasMode;
  setCanvasMode: (mode: CanvasMode) => void;

  // Confidence filter
  confidenceFilter: ConfidenceFilter;
  setConfidenceFilter: (filter: ConfidenceFilter) => void;

  // Unsaved changes tracker
  pendingChanges: Set<number>;
  markPending: (annotationId: number) => void;
  clearPending: () => void;
}

export const useAnnotationStore = create<AnnotationStore>((set) => ({
  selectedImageId: null,
  setSelectedImageId: (id) =>
    set({ selectedImageId: id, selectedAnnotationId: null }),

  selectedAnnotationId: null,
  setSelectedAnnotationId: (id) => set({ selectedAnnotationId: id }),

  canvasMode: 'select',
  setCanvasMode: (mode) => set({ canvasMode: mode }),

  confidenceFilter: 'all',
  setConfidenceFilter: (filter) => set({ confidenceFilter: filter }),

  pendingChanges: new Set(),
  markPending: (annotationId) =>
    set((state) => ({
      pendingChanges: new Set(state.pendingChanges).add(annotationId),
    })),
  clearPending: () => set({ pendingChanges: new Set() }),
}));
