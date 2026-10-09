'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { labelColor, type Annotation, LABEL_COLORS } from '@/lib/annotation-types';

// ── Load canvas only on the client (Konva needs window + canvas native module)
const AnnotationCanvas = dynamic(() => import('@/components/AnnotationCanvas'), {
  ssr: false,
  loading: () => (
    <div className="flex-1 flex items-center justify-center bg-gray-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3" />
        <p className="text-sm text-gray-400">Loading canvas…</p>
      </div>
    </div>
  ),
});

// ── Types ─────────────────────────────────────────────────────────────────────

interface ImageInfo {
  id: string; project_id: string; filename: string; original_filename: string;
  width?: number; height?: number; status: string; upload_date: string; file_url: string;
}

interface AnnotationCreate {
  image_id: string; x1: number; y1: number; x2: number; y2: number;
  text: string; label: string;
}

interface OcrResult { engine: string; message: string; annotations: Annotation[]; note?: string; }

// ── API ───────────────────────────────────────────────────────────────────────

const API = 'http://localhost:8000';

async function fetchImage(id: string): Promise<ImageInfo> {
  const r = await fetch(`${API}/api/images/${id}`);
  if (!r.ok) throw new Error('image fetch failed');
  return r.json();
}
async function fetchAnnotations(id: string): Promise<Annotation[]> {
  const r = await fetch(`${API}/api/images/${id}/annotations`);
  if (!r.ok) throw new Error('annotations fetch failed');
  return r.json();
}
async function createAnnotation(ann: AnnotationCreate): Promise<Annotation> {
  const r = await fetch(`${API}/api/images/${ann.image_id}/annotations`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ann),
  });
  if (!r.ok) throw new Error('create failed');
  return r.json();
}
async function updateAnnotation(id: string, ann: AnnotationCreate): Promise<Annotation> {
  const r = await fetch(`${API}/api/annotations/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ann),
  });
  if (!r.ok) throw new Error('update failed');
  return r.json();
}
async function deleteAnnotation(id: string): Promise<void> {
  const r = await fetch(`${API}/api/annotations/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error('delete failed');
}
async function runOCR(imageId: string): Promise<OcrResult> {
  const r = await fetch(`${API}/api/images/${imageId}/ocr`, { method: 'POST' });
  if (!r.ok) throw new Error('OCR failed');
  return r.json();
}
async function runFinetunedOCR(imageId: string): Promise<OcrResult> {
  const r = await fetch(`${API}/api/images/${imageId}/ocr/finetuned`, { method: 'POST' });
  if (!r.ok) throw new Error('Finetuned OCR failed');
  return r.json();
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AnnotatePage() {
  const params  = useParams();
  const imageId = params.id as string;
  const qc      = useQueryClient();

  const [mode,      setMode]      = useState<'select' | 'draw'>('select');
  const [showHelp,  setShowHelp]  = useState(false);
  const [ocrMsg,    setOcrMsg]    = useState<string | null>(null);

  const [scale,      setScale]      = useState(1);
  const [offset,     setOffset]     = useState({ x: 0, y: 0 });
  const [imgEl,      setImgEl]      = useState<HTMLImageElement | null>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
  const [drawing,    setDrawing]    = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [selected,   setSelected]   = useState<Annotation | null>(null);
  const [editText,   setEditText]   = useState('');
  const [editLabel,  setEditLabel]  = useState('Marathi');

  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef     = useRef<any>(null);
  const isDrawing    = useRef(false);
  const panStart     = useRef<{ px: number; py: number; ox: number; oy: number } | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────────
  const { data: imageInfo, isLoading: imgLoading } = useQuery({
    queryKey: ['image', imageId], queryFn: () => fetchImage(imageId),
  });
  const { data: annotations = [] } = useQuery({
    queryKey: ['annotations', imageId], queryFn: () => fetchAnnotations(imageId),
  });

  const createMut = useMutation({
    mutationFn: createAnnotation,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['annotations', imageId] }),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, ann }: { id: string; ann: AnnotationCreate }) => updateAnnotation(id, ann),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['annotations', imageId] }),
  });
  const deleteMut = useMutation({
    mutationFn: deleteAnnotation,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['annotations', imageId] }); setSelected(null); },
  });
  const ocrMut = useMutation({
    mutationFn: () => runOCR(imageId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['annotations', imageId] });
      setOcrMsg(`${data.engine === 'IndicPhotoOCR' ? '✓ IndicPhotoOCR' : '⚠ Mock OCR'} — ${data.message}${data.note ? ` (${data.note})` : ''}`);
      setTimeout(() => setOcrMsg(null), 6000);
    },
    onError: (err: any) => {
      setOcrMsg(`✗ OCR failed: ${err.message}`);
      setTimeout(() => setOcrMsg(null), 5000);
    },
  });
  const finetunedMut = useMutation({
    mutationFn: () => runFinetunedOCR(imageId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['annotations', imageId] });
      setOcrMsg(`✓ ${data.engine} — ${data.message}${data.note ? ` (${data.note})` : ''}`);
      setTimeout(() => setOcrMsg(null), 6000);
    },
    onError: (err: any) => {
      setOcrMsg(`✗ Finetuned OCR failed: ${err.message}`);
      setTimeout(() => setOcrMsg(null), 5000);
    },
  });

  // ── Fit image to container ───────────────────────────────────────────────────
  const fitImage = useCallback((img: HTMLImageElement, container: HTMLDivElement | null) => {
    if (!container) return;
    const cw  = container.offsetWidth;
    const ch  = container.offsetHeight;
    const pad = 60;
    const s   = Math.min((cw - pad * 2) / img.naturalWidth, (ch - pad * 2) / img.naturalHeight);
    setScale(Math.max(0.05, s));
    setOffset({
      x: Math.round((cw - img.naturalWidth  * s) / 2),
      y: Math.round((ch - img.naturalHeight * s) / 2),
    });
  }, []);

  useEffect(() => {
    if (!imageInfo) return;
    const img    = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload  = () => { setImgEl(img); fitImage(img, containerRef.current); };
    img.src     = `${API}${imageInfo.file_url}`;
  }, [imageInfo, fitImage]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      setCanvasSize({ w: el.offsetWidth, h: el.offsetHeight });
      if (imgEl) fitImage(imgEl, el);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [imgEl, fitImage]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 's' || e.key === 'S') { setMode('select'); e.preventDefault(); }
      if (e.key === 'd' || e.key === 'D') { setMode('draw');   e.preventDefault(); }
      if (e.key === 'Escape') { setSelected(null); setDrawing(null); isDrawing.current = false; }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selected) { deleteMut.mutate(selected.id); e.preventDefault(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected, deleteMut]);

  useEffect(() => {
    if (!selected) return;
    const live = annotations.find(a => a.id === selected.id);
    setEditText(live?.text  ?? selected.text);
    setEditLabel(live?.label ?? selected.label);
  }, [selected, annotations]);

  const toImg = (stage: any) => {
    const p = stage.getPointerPosition();
    return { x: (p.x - offset.x) / scale, y: (p.y - offset.y) / scale };
  };

  const onMouseDown = (e: any) => {
    if (e.evt.button === 1) {
      panStart.current = { px: e.evt.clientX, py: e.evt.clientY, ox: offset.x, oy: offset.y };
      e.evt.preventDefault();
      return;
    }
    if (mode !== 'draw') return;
    const { x, y } = toImg(e.target.getStage());
    isDrawing.current = true;
    setDrawing({ x, y, w: 0, h: 0 });
  };

  const onMouseMove = (e: any) => {
    if (panStart.current) {
      const dx = e.evt.clientX - panStart.current.px;
      const dy = e.evt.clientY - panStart.current.py;
      setOffset({ x: panStart.current.ox + dx, y: panStart.current.oy + dy });
      return;
    }
    if (!isDrawing.current || !drawing) return;
    const { x, y } = toImg(e.target.getStage());
    setDrawing(d => d ? { ...d, w: x - d.x, h: y - d.y } : null);
  };

  const onMouseUp = () => {
    panStart.current = null;
    if (!isDrawing.current || !drawing) return;
    isDrawing.current = false;
    const minPx = 8 / scale;
    if (Math.abs(drawing.w) < minPx || Math.abs(drawing.h) < minPx) { setDrawing(null); return; }
    const x1 = Math.min(drawing.x, drawing.x + drawing.w);
    const y1 = Math.min(drawing.y, drawing.y + drawing.h);
    const x2 = Math.max(drawing.x, drawing.x + drawing.w);
    const y2 = Math.max(drawing.y, drawing.y + drawing.h);
    createMut.mutate({ image_id: imageId, x1, y1, x2, y2, text: '', label: 'Marathi' });
    setDrawing(null);
    setMode('select');
  };

  const onWheel = (e: any) => {
    e.evt.preventDefault();
    const stage    = stageRef.current;
    if (!stage)    return;
    const ptr      = stage.getPointerPosition();
    const factor   = e.evt.deltaY < 0 ? 1.12 : 1 / 1.12;
    const newScale = Math.max(0.05, Math.min(20, scale * factor));
    const imgX     = (ptr.x - offset.x) / scale;
    const imgY     = (ptr.y - offset.y) / scale;
    setOffset({ x: ptr.x - imgX * newScale, y: ptr.y - imgY * newScale });
    setScale(newScale);
  };

  const saveSelected = () => {
    if (!selected) return;
    updateMut.mutate({
      id: selected.id,
      ann: { image_id: selected.image_id, x1: selected.x1, y1: selected.y1, x2: selected.x2, y2: selected.y2, text: editText, label: editLabel },
    });
    setSelected({ ...selected, text: editText, label: editLabel });
  };

  const onBoxMoved = (id: string, x1: number, y1: number, x2: number, y2: number) => {
    const ann = annotations.find(a => a.id === id);
    if (!ann) return;
    updateMut.mutate({ id, ann: { image_id: ann.image_id, x1, y1, x2, y2, text: ann.text, label: ann.label } });
    if (selected?.id === id) setSelected({ ...selected, x1, y1, x2, y2 });
  };

  const resetView = () => { if (imgEl) fitImage(imgEl, containerRef.current); };

  if (imgLoading) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4" />
        <p>Loading image…</p>
      </div>
    </div>
  );
  if (!imageInfo) return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <p className="text-red-400 mr-4">Image not found</p>
      <Link href="/projects" className="text-blue-400 hover:text-blue-300">← Back to projects</Link>
    </div>
  );

  const LABELS = Object.keys(LABEL_COLORS);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white overflow-hidden">

      {/* ── Header ── */}
      <div className="flex-none bg-gray-900 border-b border-gray-700 px-4 py-2 flex items-center gap-3">
        <Link href={`/projects/${imageInfo.project_id}`}
          className="text-gray-400 hover:text-white text-sm whitespace-nowrap">
          ← Back
        </Link>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate">{imageInfo.original_filename}</p>
          {imgEl && (
            <p className="text-xs text-gray-400">
              {imgEl.naturalWidth} × {imgEl.naturalHeight}px &nbsp;·&nbsp;
              {annotations.length} annotation{annotations.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>

        {/* Mode toggle */}
        <div className="flex bg-gray-800 rounded-lg p-0.5 text-sm">
          {(['select', 'draw'] as const).map(m => (
            <button key={m} onClick={() => setMode(m)}
              title={m === 'select' ? 'S' : 'D'}
              className={`px-3 py-1 rounded capitalize transition-colors ${
                mode === m ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
              {m}
            </button>
          ))}
        </div>

        <button onClick={() => ocrMut.mutate()} disabled={ocrMut.isPending || finetunedMut.isPending}
          className="px-3 py-1 text-sm rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-wait">
          {ocrMut.isPending ? '⏳ Running…' : '▶ Run OCR'}
        </button>

        <button onClick={() => finetunedMut.mutate()} disabled={ocrMut.isPending || finetunedMut.isPending}
          className="px-3 py-1 text-sm rounded bg-teal-600 hover:bg-teal-500 disabled:opacity-40 disabled:cursor-wait"
          title="Run our finetuned Marathi scene-text recogniser">
          {finetunedMut.isPending ? '⏳ Running…' : '▶ Finetuned OCR'}
        </button>

        <button onClick={resetView} className="px-3 py-1 text-sm rounded bg-gray-700 hover:bg-gray-600">Fit</button>

        <div className="flex items-center bg-gray-800 rounded-lg overflow-hidden text-sm">
          <button onClick={() => {
            const ns = Math.max(0.05, scale / 1.25);
            const cx = (canvasSize.w / 2 - offset.x) / scale;
            const cy = (canvasSize.h / 2 - offset.y) / scale;
            setOffset({ x: canvasSize.w / 2 - cx * ns, y: canvasSize.h / 2 - cy * ns });
            setScale(ns);
          }} className="px-2 py-1 hover:bg-gray-700 text-gray-300 hover:text-white select-none">−</button>
          <span className="px-2 py-1 text-gray-400 tabular-nums min-w-[52px] text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => {
            const ns = Math.min(20, scale * 1.25);
            const cx = (canvasSize.w / 2 - offset.x) / scale;
            const cy = (canvasSize.h / 2 - offset.y) / scale;
            setOffset({ x: canvasSize.w / 2 - cx * ns, y: canvasSize.h / 2 - cy * ns });
            setScale(ns);
          }} className="px-2 py-1 hover:bg-gray-700 text-gray-300 hover:text-white select-none">+</button>
        </div>

        <button onClick={() => setShowHelp(true)} className="px-3 py-1 text-sm rounded bg-gray-700 hover:bg-gray-600">?</button>
      </div>

      {/* ── OCR toast ── */}
      {ocrMsg && (
        <div className={`flex-none text-sm px-4 py-2 border-b ${
          ocrMsg.startsWith('✓') ? 'bg-emerald-900 border-emerald-700 text-emerald-100' :
          ocrMsg.startsWith('⚠') ? 'bg-yellow-900 border-yellow-700 text-yellow-100' :
                                    'bg-red-900 border-red-700 text-red-100'}`}>
          {ocrMsg}
        </div>
      )}

      {/* ── Main ── */}
      <div className="flex flex-1 min-h-0">

        {/* Canvas */}
        <div ref={containerRef}
          className={`flex-1 relative overflow-hidden ${mode === 'draw' ? 'cursor-crosshair' : 'cursor-default'}`}
          style={{
            backgroundColor: '#1a1a2e',
            backgroundImage: `
              linear-gradient(45deg, #262640 25%, transparent 25%),
              linear-gradient(-45deg, #262640 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #262640 75%),
              linear-gradient(-45deg, transparent 75%, #262640 75%)`,
            backgroundSize: '20px 20px',
            backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          }}
        >
          {canvasSize.w > 0 && (
            <AnnotationCanvas
              width={canvasSize.w} height={canvasSize.h}
              imgEl={imgEl} scale={scale} offset={offset}
              annotations={annotations} selectedId={selected?.id ?? null}
              drawing={drawing} mode={mode} stageRef={stageRef}
              onMouseDown={onMouseDown} onMouseMove={onMouseMove}
              onMouseUp={onMouseUp} onWheel={onWheel}
              onSelect={setSelected} onDeselect={() => setSelected(null)}
              onBoxMoved={onBoxMoved}
            />
          )}
          <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-1.5
            bg-gray-950/70 backdrop-blur-sm border-t border-gray-800 pointer-events-none select-none">
            <p className="text-xs text-gray-500">
              {mode === 'draw' ? '✏ Drag to draw · ESC to cancel' : '↖ Click to select · Drag to move · Scroll to zoom · Middle-drag to pan'}
            </p>
            {imgEl && <p className="text-xs text-gray-600 tabular-nums">{imgEl.naturalWidth} × {imgEl.naturalHeight} px</p>}
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-72 flex flex-col bg-gray-800 border-l border-gray-700 overflow-hidden">
          {selected ? (
            <div className="p-3 border-b border-gray-700 space-y-2 flex-none">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">Edit annotation</span>
                <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-white text-lg leading-none">×</button>
              </div>
              {selected.confidence !== undefined && (
                <p className="text-xs text-gray-400">
                  Confidence:&nbsp;
                  <span className={`font-semibold ${selected.confidence > 0.9 ? 'text-emerald-400' : selected.confidence > 0.75 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {(selected.confidence * 100).toFixed(1)}%
                  </span>
                </p>
              )}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Transcription</label>
                <input type="text" value={editText} onChange={e => setEditText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') saveSelected(); }}
                  className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm text-white placeholder-gray-500"
                  placeholder="Type text visible in this box…" autoFocus />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Label</label>
                <div className="grid grid-cols-3 gap-1">
                  {LABELS.map(lbl => {
                    const clr = labelColor(lbl);
                    return (
                      <button key={lbl} onClick={() => setEditLabel(lbl)}
                        style={{ borderColor: editLabel === lbl ? clr : 'transparent', color: editLabel === lbl ? clr : undefined }}
                        className={`py-1 rounded text-xs border-2 transition-colors ${editLabel === lbl ? 'bg-gray-700' : 'bg-gray-900 text-gray-400 hover:bg-gray-700'}`}>
                        {lbl}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button onClick={saveSelected} disabled={updateMut.isPending}
                  className="flex-1 py-1.5 rounded text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-40">Save</button>
                <button onClick={() => deleteMut.mutate(selected.id)} disabled={deleteMut.isPending}
                  className="px-3 py-1.5 rounded text-sm bg-red-700 hover:bg-red-600 disabled:opacity-40">Delete</button>
              </div>
            </div>
          ) : (
            <div className="p-3 border-b border-gray-700 flex-none">
              <p className="text-xs text-gray-500">
                {mode === 'draw' ? 'Draw mode — drag on the image to create a bounding box.' : 'Select mode — click a box to edit its text and label.'}
              </p>
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {annotations.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-10">No annotations yet.<br />Switch to Draw mode and drag on the canvas.</p>
            ) : annotations.map((ann, idx) => {
              const color = labelColor(ann.label);
              return (
                <button key={ann.id} onClick={() => setSelected(ann)}
                  className={`w-full text-left px-2 py-2 rounded transition-colors ${selected?.id === ann.id ? 'bg-gray-600 ring-1 ring-white/20' : 'bg-gray-900 hover:bg-gray-700'}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 shrink-0">#{idx + 1}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded shrink-0" style={{ background: `${color}33`, color }}>{ann.label}</span>
                    {ann.confidence !== undefined && (
                      <span className={`text-xs ml-auto shrink-0 ${ann.confidence > 0.9 ? 'text-emerald-400' : ann.confidence > 0.75 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {(ann.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  {ann.text && <p className="text-sm mt-0.5 truncate" title={ann.text}>{ann.text}</p>}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Help modal */}
      {showHelp && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowHelp(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-80 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">Keyboard Shortcuts</h3>
              <button onClick={() => setShowHelp(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <table className="w-full text-sm border-separate border-spacing-y-1">
              <tbody>
                {[['S','Select mode'],['D','Draw mode'],['Enter','Save selected'],['Del / Backspace','Delete selected'],['Esc','Deselect / cancel draw'],['Scroll wheel','Zoom in / out'],['Middle-drag','Pan'],['Drag a box','Move it (Select mode)']].map(([k, v]) => (
                  <tr key={k}>
                    <td className="pr-3 py-0.5"><kbd className="bg-gray-700 px-2 py-0.5 rounded text-xs whitespace-nowrap">{k}</kbd></td>
                    <td className="py-0.5 text-gray-300">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
