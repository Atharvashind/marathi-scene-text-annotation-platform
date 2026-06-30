'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchImages, deleteImage } from '@/lib/api';
import { useAnnotationStore } from '@/store/annotationStore';
import type { AnnotationStatus, ImageRecord } from '@/types';
import { API_BASE } from '@/lib/api';

const STATUS_BADGE: Record<AnnotationStatus, { label: string; cls: string }> = {
  Uploaded: { label: 'Uploaded', cls: 'bg-gray-700 text-gray-200' },
  OCR_Completed: { label: 'OCR Done', cls: 'bg-blue-700 text-blue-100' },
  Under_Review: { label: 'In Review', cls: 'bg-yellow-600 text-yellow-50' },
  Approved: { label: 'Approved', cls: 'bg-green-700 text-green-100' },
};

export default function ImageGallery() {
  const { data: images = [], isLoading } = useQuery({
    queryKey: ['images'],
    queryFn: fetchImages,
  });

  const queryClient = useQueryClient();
  const { selectedImageId, setSelectedImageId } = useAnnotationStore();
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // SSE for real-time status updates
  const esRef = useRef<EventSource | null>(null);
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`);
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        // Only refresh gallery list for status changes — don't touch canvas queries
        if (['status_changed', 'ocr_completed', 'image_approved',
             'batch_ocr_progress', 'batch_ocr_finished', 'batch_ocr_image_failed']
            .includes(event.type)) {
          queryClient.invalidateQueries({ queryKey: ['images'] });
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, [queryClient]);

  const handleDelete = async (imageId: number) => {
    setDeleting(true);
    try {
      await deleteImage(imageId);
      if (selectedImageId === imageId) setSelectedImageId(null);
      queryClient.invalidateQueries({ queryKey: ['images'] });
    } catch (err) {
      alert(`Delete failed: ${err}`);
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
    }
  };

  if (isLoading) {
    return (
      <aside className="w-64 bg-gray-900 border-r border-gray-700 p-3 overflow-y-auto flex items-center justify-center">
        <span className="text-gray-400 text-sm">Loading…</span>
      </aside>
    );
  }

  const uploadedCount = images.filter(img => img.status === 'Uploaded').length;

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-700 overflow-y-auto flex flex-col">
      <div className="p-3 border-b border-gray-700">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Images ({images.length})
          {uploadedCount > 0 && (
            <span className="ml-2 text-blue-400">{uploadedCount} pending OCR</span>
          )}
        </h2>
      </div>

      <ul className="flex-1 divide-y divide-gray-800">
        {images.map((img: ImageRecord) => {
          const badge = STATUS_BADGE[img.status];
          const isSelected = img.id === selectedImageId;
          const isConfirming = confirmDeleteId === img.id;

          return (
            <li key={img.id} className="relative group">
              <button
                onClick={() => setSelectedImageId(img.id)}
                className={`w-full text-left p-3 hover:bg-gray-800 transition-colors ${
                  isSelected ? 'bg-gray-800 border-l-2 border-blue-500' : ''
                }`}
              >
                {/* Thumbnail */}
                <div className="w-full h-20 bg-gray-800 rounded mb-2 overflow-hidden flex items-center justify-center">
                  <img
                    src={`${API_BASE}/api/images/${img.id}/thumbnail`}
                    alt={img.filename}
                    className="object-contain w-full h-full"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                </div>
                <p className="text-xs text-gray-200 truncate pr-6" title={img.filename}>
                  {img.filename}
                </p>
                <span className={`mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded ${badge.cls}`}>
                  {badge.label}
                </span>
              </button>

              {/* Delete button — shown on hover */}
              {!isConfirming && (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(img.id); }}
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity
                             w-6 h-6 flex items-center justify-center rounded bg-red-800 hover:bg-red-600
                             text-white text-xs"
                  title="Delete image"
                >
                  ✕
                </button>
              )}

              {/* Confirm dialog */}
              {isConfirming && (
                <div className="absolute inset-0 bg-gray-900/95 flex flex-col items-center justify-center gap-2 p-3 z-10">
                  <p className="text-xs text-gray-200 text-center">Delete this image and all its annotations?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(img.id)}
                      disabled={deleting}
                      className="px-3 py-1 text-xs bg-red-700 hover:bg-red-600 text-white rounded disabled:opacity-50"
                    >
                      {deleting ? 'Deleting…' : 'Delete'}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}

        {images.length === 0 && (
          <li className="p-4 text-center text-gray-500 text-sm">
            No images yet. Upload some to get started.
          </li>
        )}
      </ul>
    </aside>
  );
}
