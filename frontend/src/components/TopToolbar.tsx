'use client';

import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAnnotationStore } from '@/store/annotationStore';
import { uploadImages, runOCR, downloadExport } from '@/lib/api';
import type { ExportFormat } from '@/types';

const ACCEPTED_MIME = 'image/jpeg,image/png,image/webp';

export default function TopToolbar() {
  const queryClient = useQueryClient();
  const { selectedImageId, canvasMode, setCanvasMode } = useAnnotationStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isRunningOCR, setIsRunningOCR] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    try {
      const results = await uploadImages(files);
      const failed = results.filter((r) => !r.success);
      await queryClient.invalidateQueries({ queryKey: ['images'] });
      if (failed.length) {
        showToast(`${failed.length} file(s) failed to upload`, 'error');
      } else {
        showToast(`${results.length} image(s) uploaded`, 'success');
      }
    } catch (err) {
      showToast(String(err), 'error');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRunOCR = async () => {
    if (!selectedImageId) return;
    setIsRunningOCR(true);
    try {
      await runOCR(selectedImageId);
      // Force-refetch annotations, image status, and gallery
      await queryClient.invalidateQueries({ queryKey: ['annotations', selectedImageId] });
      await queryClient.invalidateQueries({ queryKey: ['image', selectedImageId] });
      await queryClient.invalidateQueries({ queryKey: ['images'] });
      await queryClient.refetchQueries({ queryKey: ['annotations', selectedImageId] });
      showToast('OCR completed — annotations loaded', 'success');
    } catch (err) {
      showToast(`OCR failed: ${err}`, 'error');
    } finally {
      setIsRunningOCR(false);
    }
  };

  const handleSave = async () => {
    // Save is handled via individual PATCH calls already; this flushes the React Query cache
    setIsSaving(true);
    try {
      await queryClient.invalidateQueries({ queryKey: ['annotations', selectedImageId] });
      showToast('Saved', 'success');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async (format: ExportFormat) => {
    setShowExportMenu(false);
    if (!selectedImageId) return;
    try {
      await downloadExport(selectedImageId, format);
    } catch (err) {
      showToast(`Export failed: ${err}`, 'error');
    }
  };

  const noImage = !selectedImageId;
  const disabledCls = 'opacity-40 cursor-not-allowed';
  const btnCls =
    'px-3 py-1.5 text-sm rounded font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <header className="h-12 bg-gray-900 border-b border-gray-700 flex items-center gap-2 px-4 relative z-10">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_MIME}
        className="hidden"
        onChange={handleUpload}
        data-testid="file-input"
      />

      {/* Upload */}
      <button
        className={`${btnCls} bg-blue-600 hover:bg-blue-500 text-white`}
        onClick={() => fileInputRef.current?.click()}
        title="Upload images"
      >
        Upload Images
      </button>

      <div className="w-px h-6 bg-gray-700 mx-1" />

      {/* Mode toggle */}
      <button
        className={`${btnCls} ${canvasMode === 'select' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}`}
        onClick={() => setCanvasMode('select')}
        title="Select / move annotations"
      >
        Select
      </button>
      <button
        className={`${btnCls} ${canvasMode === 'draw' ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}`}
        onClick={() => setCanvasMode('draw')}
        title="Draw new annotation"
      >
        Draw
      </button>

      <div className="w-px h-6 bg-gray-700 mx-1" />

      {/* Run OCR */}
      <button
        className={`${btnCls} bg-purple-700 hover:bg-purple-600 text-white`}
        disabled={noImage || isRunningOCR}
        onClick={handleRunOCR}
        title={noImage ? 'Select an image first' : 'Run OCR on this image'}
      >
        {isRunningOCR ? 'Running…' : 'Run OCR'}
      </button>

      {/* Save */}
      <button
        className={`${btnCls} bg-green-700 hover:bg-green-600 text-white`}
        disabled={noImage || isSaving}
        onClick={handleSave}
        title={noImage ? 'Select an image first' : 'Save annotations'}
      >
        {isSaving ? 'Saving…' : 'Save'}
      </button>

      {/* Export */}
      <div className="relative">
        <button
          className={`${btnCls} bg-orange-700 hover:bg-orange-600 text-white`}
          disabled={noImage}
          onClick={() => setShowExportMenu((v) => !v)}
          title={noImage ? 'Select an image first' : 'Export annotations'}
        >
          Export ▾
        </button>
        {showExportMenu && (
          <div className="absolute top-full mt-1 left-0 bg-gray-800 border border-gray-600 rounded shadow-lg w-40 z-20">
            {(['yolo', 'coco', 'labelstudio', 'custom_json'] as ExportFormat[]).map((fmt) => (
              <button
                key={fmt}
                onClick={() => handleExport(fmt)}
                className="block w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-gray-700"
              >
                {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-4 right-4 px-4 py-2 rounded shadow-lg text-sm text-white z-50 ${
            toast.type === 'success' ? 'bg-green-700' : 'bg-red-700'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </header>
  );
}
