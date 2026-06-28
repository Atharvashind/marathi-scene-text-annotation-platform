'use client';

import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchImages } from '@/lib/api';
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

  // Subscribe to SSE for real-time status updates
  const esRef = useRef<EventSource | null>(null);
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`);
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (
          event.type === 'status_changed' ||
          event.type === 'ocr_completed' ||
          event.type === 'image_approved'
        ) {
          queryClient.invalidateQueries({ queryKey: ['images'] });
        }
      } catch {
        // ignore parse errors
      }
    };
    return () => es.close();
  }, [queryClient]);

  if (isLoading) {
    return (
      <aside className="w-64 bg-gray-900 border-r border-gray-700 p-3 overflow-y-auto flex items-center justify-center">
        <span className="text-gray-400 text-sm">Loading…</span>
      </aside>
    );
  }

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-700 overflow-y-auto flex flex-col">
      <div className="p-3 border-b border-gray-700">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Images ({images.length})
        </h2>
      </div>
      <ul className="flex-1 divide-y divide-gray-800">
        {images.map((img: ImageRecord) => {
          const badge = STATUS_BADGE[img.status];
          const isSelected = img.id === selectedImageId;
          return (
            <li key={img.id}>
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
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
                <p className="text-xs text-gray-200 truncate" title={img.filename}>
                  {img.filename}
                </p>
                <span
                  className={`mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded ${badge.cls}`}
                >
                  {badge.label}
                </span>
              </button>
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
