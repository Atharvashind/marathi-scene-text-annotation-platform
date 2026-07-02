'use client';

import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import dynamic from 'next/dynamic';
import {
  fetchImages, fetchAnnotations, createAnnotation,
  updateAnnotation, deleteAnnotation, updateImageStatus,
  runOCR, runBatchOCR, uploadImages as apiUploadImages,
  downloadExport,
} from '@/lib/api';
import { useAnnotationStore } from '@/store/annotationStore';
import TopToolbar from '@/components/TopToolbar';
import ImageGallery from '@/components/ImageGallery';
import AnnotationPanel from '@/components/AnnotationPanel';
import StatsDashboard from '@/components/StatsDashboard';
import type { AnnotationCreate } from '@/types';
import { API_BASE } from '@/lib/api';

const AnnotationCanvas = dynamic(() => import('@/components/AnnotationCanvas'), { ssr: false });

export default function ImagesPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { selectedImageId } = useAnnotationStore();
  const [showStats, setShowStats] = useState(false);

  const { data: image } = useQuery({
    queryKey: ['image', projectId, selectedImageId],
    queryFn: () => fetchImages(projectId).then(imgs => imgs.find(i => i.id === selectedImageId) ?? null),
    enabled: !!selectedImageId,
  });

  const { data: annotations = [] } = useQuery({
    queryKey: ['annotations', projectId, selectedImageId],
    queryFn: () => fetchAnnotations(projectId, selectedImageId!),
    enabled: !!selectedImageId,
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['annotations', projectId, selectedImageId] });
    queryClient.invalidateQueries({ queryKey: ['image', projectId, selectedImageId] });
  }, [queryClient, projectId, selectedImageId]);

  useEffect(() => {
    if (image?.status === 'OCR_Completed' && image?.id === selectedImageId) {
      updateImageStatus(projectId, image.id, 'Under_Review').then(() => {
        queryClient.invalidateQueries({ queryKey: ['images', projectId] });
      });
    }
  }, [image?.status, image?.id, selectedImageId, projectId, queryClient]);

  const handleAnnotationCreate = useCallback(async (data: AnnotationCreate) => {
    if (!selectedImageId) return;
    await createAnnotation(projectId, selectedImageId, data);
    invalidate();
  }, [projectId, selectedImageId, invalidate]);

  const handleAnnotationUpdate = useCallback(async (id: string, x1: number, y1: number, x2: number, y2: number) => {
    await updateAnnotation(projectId, id, { x1, y1, x2, y2 });
    invalidate();
  }, [projectId, invalidate]);

  const handleAnnotationDelete = useCallback(async (id: string) => {
    await deleteAnnotation(projectId, id);
    invalidate();
  }, [projectId, invalidate]);

  const handleApprove = useCallback(async () => {
    if (!image) return;
    await updateImageStatus(projectId, image.id, 'Approved');
    queryClient.invalidateQueries({ queryKey: ['images', projectId] });
  }, [image, projectId, queryClient]);

  const handleReopen = useCallback(async () => {
    if (!image) return;
    await updateImageStatus(projectId, image.id, 'Under_Review');
    queryClient.invalidateQueries({ queryKey: ['images', projectId] });
  }, [image, projectId, queryClient]);

  const isApproved = image?.status === 'Approved';
  const imageUrl = image ? `${API_BASE}/api/images/file/${image.storage_key}` : '';

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopToolbar projectId={projectId} />
      <div className="flex flex-1 overflow-hidden">
        <ImageGallery projectId={projectId} />
        <main className="flex-1 flex flex-col overflow-hidden">
          {image && (
            <div className="h-8 bg-gray-900 border-b border-gray-700 flex items-center px-3 gap-3 text-xs">
              <span className="text-gray-400 truncate max-w-xs">{image.filename}</span>
              <span className="text-gray-500">|</span>
              <span className="text-gray-300">{image.width} × {image.height}</span>
              <span className="text-gray-500">|</span>
              <span className={`font-medium ${isApproved ? 'text-green-400' : 'text-yellow-400'}`}>
                {image.status.replace('_', ' ')}
              </span>
              <div className="ml-auto flex gap-2">
                {!isApproved && <button onClick={handleApprove} className="px-2 py-0.5 rounded bg-green-700 hover:bg-green-600 text-white text-xs">Approve</button>}
                {isApproved && <button onClick={handleReopen} className="px-2 py-0.5 rounded bg-yellow-700 hover:bg-yellow-600 text-white text-xs">Re-open</button>}
                <button onClick={() => setShowStats(true)} className="px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs">Stats</button>
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
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
              Select an image from the gallery to start annotating
            </div>
          )}
        </main>
        <AnnotationPanel annotations={annotations} selectedImageId={selectedImageId} isLocked={isApproved} projectId={projectId} />
      </div>
      {showStats && <StatsDashboard imageId={selectedImageId} onClose={() => setShowStats(false)} projectId={projectId} />}
    </div>
  );
}
