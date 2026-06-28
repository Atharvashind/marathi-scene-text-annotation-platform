'use client';

import { useState, useCallback, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import dynamic from 'next/dynamic';

import TopToolbar from '@/components/TopToolbar';
import ImageGallery from '@/components/ImageGallery';
import AnnotationPanel from '@/components/AnnotationPanel';
import StatsDashboard from '@/components/StatsDashboard';

import { useAnnotationStore } from '@/store/annotationStore';
import {
  fetchImage,
  fetchAnnotations,
  createAnnotation,
  updateAnnotation,
  deleteAnnotation,
  updateImageStatus,
} from '@/lib/api';
import { API_BASE } from '@/lib/api';
import type { AnnotationCreate } from '@/types';

// AnnotationCanvas uses Konva which requires browser APIs — load client-side only
const AnnotationCanvas = dynamic(() => import('@/components/AnnotationCanvas'), {
  ssr: false,
});

export default function Home() {
  const queryClient = useQueryClient();
  const { selectedImageId } = useAnnotationStore();
  const [showStats, setShowStats] = useState(false);

  // Fetch selected image metadata
  const { data: image } = useQuery({
    queryKey: ['image', selectedImageId],
    queryFn: () => fetchImage(selectedImageId!),
    enabled: selectedImageId !== null,
  });

  // Fetch annotations for selected image
  const { data: annotations = [] } = useQuery({
    queryKey: ['annotations', selectedImageId],
    queryFn: () => fetchAnnotations(selectedImageId!),
    enabled: selectedImageId !== null,
  });

  const invalidateAnnotations = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['annotations', selectedImageId] });
    queryClient.invalidateQueries({ queryKey: ['image', selectedImageId] });
    queryClient.invalidateQueries({ queryKey: ['metrics', 'image', selectedImageId] });
    queryClient.invalidateQueries({ queryKey: ['metrics', 'project'] });
  }, [queryClient, selectedImageId]);

  // Auto-transition OCR_Completed → Under_Review when editor is opened
  const handleImageOpen = useCallback(async () => {
    if (!image || image.status !== 'OCR_Completed') return;
    await updateImageStatus(image.id, 'Under_Review');
    queryClient.invalidateQueries({ queryKey: ['image', image.id] });
    queryClient.invalidateQueries({ queryKey: ['images'] });
  }, [image, queryClient]);

  // React to image status changes — auto-transition and refetch annotations
  useEffect(() => {
    if (image?.status === 'OCR_Completed') {
      handleImageOpen();
    }
  }, [image?.status, handleImageOpen]);

  const handleAnnotationCreate = useCallback(
    async (data: AnnotationCreate) => {
      if (!selectedImageId) return;
      await createAnnotation(selectedImageId, data);
      invalidateAnnotations();
    },
    [selectedImageId, invalidateAnnotations]
  );

  const handleAnnotationUpdate = useCallback(
    async (id: number, x1: number, y1: number, x2: number, y2: number) => {
      await updateAnnotation(id, { x1, y1, x2, y2 });
      invalidateAnnotations();
    },
    [invalidateAnnotations]
  );

  const handleAnnotationDelete = useCallback(
    async (id: number) => {
      await deleteAnnotation(id);
      invalidateAnnotations();
    },
    [invalidateAnnotations]
  );

  const handleApprove = useCallback(async () => {
    if (!image) return;
    await updateImageStatus(image.id, 'Approved');
    queryClient.invalidateQueries({ queryKey: ['image', image.id] });
    queryClient.invalidateQueries({ queryKey: ['images'] });
  }, [image, queryClient]);

  const handleReopen = useCallback(async () => {
    if (!image) return;
    await updateImageStatus(image.id, 'Under_Review');
    queryClient.invalidateQueries({ queryKey: ['image', image.id] });
    queryClient.invalidateQueries({ queryKey: ['images'] });
  }, [image, queryClient]);

  const isApproved = image?.status === 'Approved';
  const imageUrl = image ? `${API_BASE}/api/images/${image.id}/file` : '';

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white overflow-hidden">
      {/* Top toolbar */}
      <TopToolbar />

      {/* Three-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Image gallery */}
        <ImageGallery />

        {/* Center: Canvas */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Status bar */}
          {image && (
            <div className="h-8 bg-gray-900 border-b border-gray-700 flex items-center px-3 gap-3 text-xs">
              <span className="text-gray-400 truncate max-w-xs" title={image.filename}>
                {image.filename}
              </span>
              <span className="text-gray-500">|</span>
              <span className="text-gray-300">
                {image.width} × {image.height}
              </span>
              <span className="text-gray-500">|</span>
              <span
                className={`font-medium ${
                  isApproved ? 'text-green-400' : 'text-yellow-400'
                }`}
              >
                {image.status.replace('_', ' ')}
              </span>

              <div className="ml-auto flex gap-2">
                {!isApproved && (
                  <button
                    onClick={handleApprove}
                    className="px-2 py-0.5 rounded bg-green-700 hover:bg-green-600 text-white text-xs"
                  >
                    Approve
                  </button>
                )}
                {isApproved && (
                  <button
                    onClick={handleReopen}
                    className="px-2 py-0.5 rounded bg-yellow-700 hover:bg-yellow-600 text-white text-xs"
                  >
                    Re-open
                  </button>
                )}
                <button
                  onClick={() => setShowStats(true)}
                  className="px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs"
                >
                  Stats
                </button>
              </div>
            </div>
          )}

          {image ? (
            <AnnotationCanvas
              imageUrl={imageUrl}
              imageWidth={image.width}
              imageHeight={image.height}
              annotations={annotations}
              onAnnotationCreate={handleAnnotationCreate}
              onAnnotationUpdate={handleAnnotationUpdate}
              onAnnotationDelete={handleAnnotationDelete}
              isLocked={isApproved}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-gray-500">
                <p className="text-4xl mb-3">🖼</p>
                <p className="text-sm">Select an image from the gallery to start annotating</p>
              </div>
            </div>
          )}
        </main>

        {/* Right: Annotation panel */}
        <AnnotationPanel
          annotations={annotations}
          selectedImageId={selectedImageId}
          isLocked={isApproved}
        />
      </div>

      {/* Stats modal */}
      {showStats && (
        <StatsDashboard
          imageId={selectedImageId}
          onClose={() => setShowStats(false)}
        />
      )}
    </div>
  );
}
