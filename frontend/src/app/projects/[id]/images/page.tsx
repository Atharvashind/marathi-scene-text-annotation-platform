'use client';

import { useRef, useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';

const API = 'http://localhost:8000';

interface ImageInfo {
  id: string; project_id: string; filename: string; original_filename: string;
  width?: number; height?: number; status: string; upload_date: string; file_url: string;
}
interface Project { id: string; name: string; description: string; image_count: number; }
interface Stats { total_images: number; total_annotations: number; completion_rate: number; }

async function fetchProject(id: string): Promise<Project> {
  const r = await fetch(`${API}/api/projects/${id}`); if (!r.ok) throw new Error('not found'); return r.json();
}
async function fetchImages(id: string): Promise<ImageInfo[]> {
  const r = await fetch(`${API}/api/projects/${id}/images`); if (!r.ok) throw new Error('failed'); return r.json();
}
async function fetchStats(id: string): Promise<Stats> {
  const r = await fetch(`${API}/api/projects/${id}/stats`); if (!r.ok) return { total_images: 0, total_annotations: 0, completion_rate: 0 }; return r.json();
}
async function deleteImage(imageId: string) {
  const r = await fetch(`${API}/api/images/${imageId}`, { method: 'DELETE' }); if (!r.ok) throw new Error('delete failed');
}
async function runBatchOcr(projectId: string) {
  const r = await fetch(`${API}/api/projects/${projectId}/ocr-all`, { method: 'POST' }); if (!r.ok) throw new Error('failed'); return r.json();
}

export default function ProjectImagesPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading,      setUploading]      = useState(false);
  const [uploadMsg,      setUploadMsg]      = useState<string | null>(null);
  const [batchRunning,   setBatchRunning]   = useState(false);
  const [batchMsg,       setBatchMsg]       = useState<string | null>(null);
  const [confirmDelete,  setConfirmDelete]  = useState<string | null>(null);
  const [deleting,       setDeleting]       = useState(false);
  const [batchProgress,  setBatchProgress]  = useState<{ done: number; total: number } | null>(null);

  const { data: project }      = useQuery({ queryKey: ['project', projectId], queryFn: () => fetchProject(projectId) });
  const { data: images = [], isLoading } = useQuery({ queryKey: ['project-images', projectId], queryFn: () => fetchImages(projectId), refetchInterval: batchRunning ? 3000 : false });
  const { data: stats }        = useQuery({ queryKey: ['project-stats', projectId], queryFn: () => fetchStats(projectId), refetchInterval: batchRunning ? 5000 : false });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['project-images', projectId] });
    qc.invalidateQueries({ queryKey: ['project-stats', projectId] });
    qc.invalidateQueries({ queryKey: ['project', projectId] });
  };

  // SSE for batch OCR progress
  useEffect(() => {
    const es = new EventSource(`${API}/api/projects/${projectId}/ocr-progress`);
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        if (ev.type === 'batch_ocr_started') {
          setBatchRunning(true); setBatchProgress({ done: 0, total: ev.total });
        } else if (ev.type === 'batch_ocr_progress' || ev.type === 'batch_ocr_image_failed') {
          setBatchProgress({ done: ev.completed + ev.failed, total: ev.total });
          invalidate();
        } else if (ev.type === 'batch_ocr_finished') {
          setBatchRunning(false);
          setBatchProgress(null);
          setBatchMsg(`OCR done — ${ev.completed}/${ev.total} succeeded${ev.failed ? `, ${ev.failed} failed` : ''}`);
          invalidate();
          setTimeout(() => setBatchMsg(null), 6000);
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleFiles = async (files: File[]) => {
    const imgs = files.filter(f => f.type.startsWith('image/'));
    if (!imgs.length) return;
    setUploading(true); setUploadMsg(`Uploading ${imgs.length} image${imgs.length > 1 ? 's' : ''}…`);
    try {
      const fd = new FormData();
      if (imgs.length === 1) {
        fd.append('file', imgs[0]);
        await fetch(`${API}/api/projects/${projectId}/images/upload`, { method: 'POST', body: fd });
      } else {
        imgs.forEach(f => fd.append('files', f));
        await fetch(`${API}/api/projects/${projectId}/images/upload-bulk`, { method: 'POST', body: fd });
      }
      setUploadMsg(`✓ ${imgs.length} image${imgs.length > 1 ? 's' : ''} uploaded`);
      invalidate();
      setTimeout(() => setUploadMsg(null), 4000);
    } catch (err) {
      setUploadMsg(`✗ Upload failed: ${err}`);
      setTimeout(() => setUploadMsg(null), 5000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setDeleting(true);
    try { await deleteImage(confirmDelete); invalidate(); }
    catch (err) { alert(`Delete failed: ${err}`); }
    finally { setDeleting(false); setConfirmDelete(null); }
  };

  const handleBatchOcr = async () => {
    setBatchMsg(null);
    try {
      const res = await runBatchOcr(projectId);
      if (res.queued === 0) { setBatchMsg('No images pending OCR'); setTimeout(() => setBatchMsg(null), 3000); }
      else { setBatchRunning(true); setBatchProgress({ done: 0, total: res.queued }); }
    } catch (err) { setBatchMsg(`Failed: ${err}`); }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center gap-4 flex-wrap">
        <Link href="/projects" className="text-gray-400 hover:text-white text-sm">← Projects</Link>
        <div className="flex-1 min-w-0">
          <h1 className="font-semibold truncate">{project?.name ?? '…'}</h1>
          {stats && <p className="text-xs text-gray-400">{stats.total_images} images · {stats.total_annotations} annotations · {stats.completion_rate}% done</p>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
            className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded disabled:opacity-50">
            {uploading ? 'Uploading…' : '+ Upload'}
          </button>
          <button onClick={handleBatchOcr} disabled={batchRunning || images.filter(i => i.status === 'uploaded').length === 0}
            className="px-3 py-1.5 text-sm bg-purple-700 hover:bg-purple-600 rounded disabled:opacity-50">
            {batchRunning ? 'OCR running…' : 'Run OCR on All'}
          </button>
        </div>
        <input ref={fileInputRef} type="file" multiple accept="image/*" className="hidden"
          onChange={e => handleFiles(Array.from(e.target.files ?? []))} />
      </div>

      {/* Status messages */}
      {(uploadMsg || batchMsg || batchProgress) && (
        <div className="px-6 py-2 bg-gray-900/60 border-b border-gray-800 text-sm flex items-center gap-4">
          {uploadMsg && <span className={uploadMsg.startsWith('✓') ? 'text-green-400' : uploadMsg.startsWith('✗') ? 'text-red-400' : 'text-blue-300'}>{uploadMsg}</span>}
          {batchMsg && <span className="text-purple-300">{batchMsg}</span>}
          {batchProgress && (
            <div className="flex items-center gap-2 ml-auto">
              <div className="w-32 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500 transition-all" style={{ width: `${batchProgress.total ? (batchProgress.done / batchProgress.total) * 100 : 0}%` }} />
              </div>
              <span className="text-xs text-gray-400 whitespace-nowrap">OCR: {batchProgress.done}/{batchProgress.total}</span>
            </div>
          )}
        </div>
      )}

      {/* Images grid */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {Array.from({ length: 10 }).map((_, i) => <div key={i} className="aspect-square bg-gray-800 rounded-lg animate-pulse" />)}
          </div>
        ) : images.length === 0 ? (
          <div className="text-center py-24">
            <p className="text-5xl mb-3">🖼️</p>
            <p className="text-gray-400 mb-1">No images yet</p>
            <p className="text-sm text-gray-500">Click "+ Upload" to add images</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {images.map(img => (
              <div key={img.id} className="group relative">
                <Link href={`/annotate/${img.id}`}>
                  <div className="aspect-square bg-gray-800 rounded-lg overflow-hidden border border-gray-700 group-hover:border-blue-500 transition-colors">
                    <img src={`${API}${img.file_url}`} alt={img.original_filename}
                      className="w-full h-full object-cover"
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                  </div>
                </Link>
                {/* Delete button */}
                <button onClick={() => setConfirmDelete(img.id)}
                  className="absolute top-2 right-2 bg-red-600 hover:bg-red-500 text-white rounded-full w-6 h-6 text-xs
                             opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  ✕
                </button>
                <p className="mt-1 text-xs text-gray-400 truncate" title={img.original_filename}>{img.original_filename}</p>
                <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                  img.status === 'ocr_completed' ? 'bg-green-900/70 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                  {img.status === 'ocr_completed' ? 'OCR done' : img.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setConfirmDelete(null)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold mb-2">Delete image?</h3>
            <p className="text-sm text-gray-400 mb-5">This permanently deletes the image and all its annotations.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDelete(null)} className="flex-1 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm">Cancel</button>
              <button onClick={handleDelete} disabled={deleting} className="flex-1 py-2 rounded bg-red-700 hover:bg-red-600 text-sm font-semibold disabled:opacity-50">
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
