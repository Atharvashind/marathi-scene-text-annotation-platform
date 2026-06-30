'use client';

import { useRef, useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAnnotationStore } from '@/store/annotationStore';
import { uploadImages, runOCR, runBatchOCR, downloadExport } from '@/lib/api';
import { API_BASE } from '@/lib/api';
import type { ExportFormat } from '@/types';

const ACCEPTED_MIME = 'image/jpeg,image/png,image/webp';

interface BatchProgress {
  completed: number;
  failed: number;
  total: number;
  running: boolean;
}

export default function TopToolbar() {
  const queryClient = useQueryClient();
  const { selectedImageId, canvasMode, setCanvasMode } = useAnnotationStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isRunningOCR, setIsRunningOCR] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [batch, setBatch] = useState<BatchProgress | null>(null);

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // SSE listener for batch OCR progress
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`);
    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        if (event.type === 'batch_ocr_started') {
          setBatch({ completed: 0, failed: 0, total: event.total, running: true });
        } else if (event.type === 'batch_ocr_progress') {
          setBatch({ completed: event.completed, failed: event.failed, total: event.total, running: true });
          queryClient.invalidateQueries({ queryKey: ['images'] });
        } else if (event.type === 'batch_ocr_image_failed') {
          setBatch({ completed: event.completed, failed: event.failed, total: event.total, running: true });
        } else if (event.type === 'batch_ocr_finished') {
          setBatch({ completed: event.completed, failed: event.failed, total: event.total, running: false });
          queryClient.invalidateQueries({ queryKey: ['images'] });
          showToast(
            `Batch OCR done — ${event.completed}/${event.total} succeeded${event.failed > 0 ? `, ${event.failed} failed` : ''}`,
            event.failed > 0 ? 'error' : 'success'
          );
          setTimeout(() => setBatch(null), 5000);
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, [queryClient]);

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

  const handleRunBatchOCR = async () => {
    try {
      const res = await runBatchOCR();
      if (res.queued === 0) {
        showToast('No images pending OCR', 'error');
      } else {
        showToast(`Batch OCR started for ${res.queued} images — processing in background`, 'success');
      }
    } catch (err) {
      showToast(`Batch OCR failed to start: ${err}`, 'error');
    }
  };

  const handleSave = async () => {
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
  const isBatchRunning = batch?.running ?? false;
  const btnCls = 'px-3 py-1.5 text-sm rounded font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <header className="bg-gray-900 border-b border-gray-700 flex flex-col relative z-10">
      {/* Main toolbar row */}
      <div className="h-12 flex items-center gap-2 px-4">
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

        {/* Canvas mode */}
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

        {/* Run OCR (single image) */}
        <button
          className={`${btnCls} bg-purple-700 hover:bg-purple-600 text-white`}
          disabled={noImage || isRunningOCR}
          onClick={handleRunOCR}
          title={noImage ? 'Select an image first' : 'Run OCR on selected image'}
        >
          {isRunningOCR ? 'Running…' : 'Run OCR'}
        </button>

        {/* Run OCR All */}
        <button
          className={`${btnCls} ${isBatchRunning ? 'bg-purple-900 text-purple-300' : 'bg-purple-800 hover:bg-purple-700 text-white'}`}
          disabled={isBatchRunning}
          onClick={handleRunBatchOCR}
          title="Run OCR on all uploaded images in background"
        >
          {isBatchRunning ? 'Batch running…' : 'Run OCR All'}
        </button>

        <div className="w-px h-6 bg-gray-700 mx-1" />

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
            <div className="absolute top-full mt-1 left-0 bg-gray-800 border border-gray-600 rounded shadow-lg w-44 z-20">
              {(['yolo', 'coco', 'labelstudio', 'custom_json'] as ExportFormat[]).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => handleExport(fmt)}
                  className="block w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-gray-700"
                >
                  {fmt.toUpperCase().replace('_', ' ')}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Batch OCR progress bar */}
      {batch && (
        <div className="px-4 pb-2 flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${batch.running ? 'bg-purple-500' : batch.failed > 0 ? 'bg-yellow-500' : 'bg-green-500'}`}
              style={{ width: `${batch.total > 0 ? (batch.completed / batch.total) * 100 : 0}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">
            {batch.running ? `OCR: ${batch.completed}/${batch.total}` : `Done: ${batch.completed}/${batch.total}`}
            {batch.failed > 0 && ` (${batch.failed} failed)`}
          </span>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-4 right-4 px-4 py-2 rounded shadow-lg text-sm text-white z-50 max-w-sm ${
            toast.type === 'success' ? 'bg-green-700' : 'bg-red-700'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </header>
  );
}
