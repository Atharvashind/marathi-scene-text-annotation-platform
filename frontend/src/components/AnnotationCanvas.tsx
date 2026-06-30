'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Transformer, Text, Group } from 'react-konva';
import type Konva from 'konva';
import { useAnnotationStore } from '@/store/annotationStore';
import { getConfidenceColor } from '@/utils/confidence';
import type { Annotation, AnnotationCreate } from '@/types';

interface Props {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  annotations: Annotation[];
  onAnnotationCreate: (data: AnnotationCreate) => void;
  onAnnotationUpdate: (id: number, x1: number, y1: number, x2: number, y2: number) => void;
  onAnnotationDelete: (id: number) => void;
  isLocked?: boolean;
}

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 8;
const ZOOM_STEP = 1.15;

export default function AnnotationCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  annotations,
  onAnnotationCreate,
  onAnnotationUpdate,
  onAnnotationDelete,
  isLocked = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const [drawing, setDrawing] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const transformerRef = useRef<Konva.Transformer>(null);
  const selectedRectRef = useRef<Konva.Rect>(null);

  // Zoom & pan state
  const [zoom, setZoom] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; stageX: number; stageY: number } | null>(null);

  const { canvasMode, selectedAnnotationId, setSelectedAnnotationId, confidenceFilter } =
    useAnnotationStore();

  // Load background image
  useEffect(() => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.src = imageUrl;
    img.onload = () => setBgImage(img);
  }, [imageUrl]);

  // Container resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setContainerSize({ width, height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Fit image to container on first load / image change
  useEffect(() => {
    if (!containerSize.width || !containerSize.height || !imageWidth || !imageHeight) return;
    const scaleX = containerSize.width / imageWidth;
    const scaleY = containerSize.height / imageHeight;
    const fitZoom = Math.min(scaleX, scaleY, 1);
    const centreX = (containerSize.width - imageWidth * fitZoom) / 2;
    const centreY = (containerSize.height - imageHeight * fitZoom) / 2;
    setZoom(fitZoom);
    setStagePos({ x: centreX, y: centreY });
  }, [imageWidth, imageHeight, containerSize]);

  // Attach transformer to selected rect
  useEffect(() => {
    if (!transformerRef.current) return;
    if (selectedRectRef.current) {
      transformerRef.current.nodes([selectedRectRef.current]);
    } else {
      transformerRef.current.nodes([]);
    }
    transformerRef.current.getLayer()?.batchDraw();
  }, [selectedAnnotationId]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAnnotationId !== null) {
        onAnnotationDelete(selectedAnnotationId);
        setSelectedAnnotationId(null);
      }
      // Zoom shortcuts
      if ((e.key === '=' || e.key === '+') && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleZoomIn();
      }
      if (e.key === '-' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleZoomOut();
      }
      if (e.key === '0' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        fitToScreen();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedAnnotationId, onAnnotationDelete, setSelectedAnnotationId, containerSize, imageWidth, imageHeight]);

  // ── Zoom helpers ──────────────────────────────────────────────────────────

  const zoomAroundPoint = useCallback((newZoom: number, px: number, py: number) => {
    newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
    setZoom(prev => {
      const factor = newZoom / prev;
      setStagePos(pos => ({
        x: px - (px - pos.x) * factor,
        y: py - (py - pos.y) * factor,
      }));
      return newZoom;
    });
  }, []);

  const handleZoomIn = useCallback(() => {
    const cx = containerSize.width / 2;
    const cy = containerSize.height / 2;
    setZoom(prev => {
      const next = Math.min(MAX_ZOOM, prev * ZOOM_STEP);
      const factor = next / prev;
      setStagePos(pos => ({
        x: cx - (cx - pos.x) * factor,
        y: cy - (cy - pos.y) * factor,
      }));
      return next;
    });
  }, [containerSize]);

  const handleZoomOut = useCallback(() => {
    const cx = containerSize.width / 2;
    const cy = containerSize.height / 2;
    setZoom(prev => {
      const next = Math.max(MIN_ZOOM, prev / ZOOM_STEP);
      const factor = next / prev;
      setStagePos(pos => ({
        x: cx - (cx - pos.x) * factor,
        y: cy - (cy - pos.y) * factor,
      }));
      return next;
    });
  }, [containerSize]);

  const fitToScreen = useCallback(() => {
    const scaleX = containerSize.width / imageWidth;
    const scaleY = containerSize.height / imageHeight;
    const fitZoom = Math.min(scaleX, scaleY, 1);
    const centreX = (containerSize.width - imageWidth * fitZoom) / 2;
    const centreY = (containerSize.height - imageHeight * fitZoom) / 2;
    setZoom(fitZoom);
    setStagePos({ x: centreX, y: centreY });
  }, [containerSize, imageWidth, imageHeight]);

  const resetZoom = useCallback(() => {
    const centreX = (containerSize.width - imageWidth) / 2;
    const centreY = (containerSize.height - imageHeight) / 2;
    setZoom(1);
    setStagePos({ x: centreX, y: centreY });
  }, [containerSize, imageWidth, imageHeight]);

  // Mouse wheel zoom
  const handleWheel = useCallback((e: Konva.KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    const direction = e.evt.deltaY > 0 ? -1 : 1;
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom * (direction > 0 ? ZOOM_STEP : 1 / ZOOM_STEP)));
    zoomAroundPoint(newZoom, pointer.x, pointer.y);
  }, [zoom, zoomAroundPoint]);

  // ── Pan logic (Space + drag, or middle mouse) ─────────────────────────────

  const handleMouseDown = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    const isMiddleMouse = e.evt.button === 1;
    const isSpacePan = isPanning;

    if (isMiddleMouse || isSpacePan) {
      e.evt.preventDefault();
      panStart.current = {
        x: e.evt.clientX,
        y: e.evt.clientY,
        stageX: stagePos.x,
        stageY: stagePos.y,
      };
      return;
    }

    if (isLocked) return;

    if (canvasMode !== 'draw') {
      if (e.target === e.target.getStage()) setSelectedAnnotationId(null);
      return;
    }

    const stage = e.target.getStage();
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    // Convert from stage coords to image coords
    const imgX = (pos.x - stagePos.x) / zoom;
    const imgY = (pos.y - stagePos.y) / zoom;
    setDrawing({ x: imgX, y: imgY, w: 0, h: 0 });
  }, [isPanning, canvasMode, zoom, stagePos, setSelectedAnnotationId, isLocked]);

  const handleMouseMove = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    // Pan
    if (panStart.current) {
      const dx = e.evt.clientX - panStart.current.x;
      const dy = e.evt.clientY - panStart.current.y;
      setStagePos({ x: panStart.current.stageX + dx, y: panStart.current.stageY + dy });
      return;
    }

    if (!drawing) return;
    const stage = stageRef.current;
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const imgX = (pos.x - stagePos.x) / zoom;
    const imgY = (pos.y - stagePos.y) / zoom;
    setDrawing(d => d ? { ...d, w: imgX - d.x, h: imgY - d.y } : null);
  }, [drawing, zoom, stagePos]);

  const handleMouseUp = useCallback(() => {
    if (panStart.current) {
      panStart.current = null;
      return;
    }

    if (!drawing) return;
    const minSize = 5;
    if (Math.abs(drawing.w) > minSize && Math.abs(drawing.h) > minSize) {
      const x1 = drawing.w >= 0 ? drawing.x : drawing.x + drawing.w;
      const y1 = drawing.h >= 0 ? drawing.y : drawing.y + drawing.h;
      onAnnotationCreate({
        x1, y1,
        x2: x1 + Math.abs(drawing.w),
        y2: y1 + Math.abs(drawing.h),
      });
    }
    setDrawing(null);
  }, [drawing, onAnnotationCreate]);

  // Space bar for pan mode
  useEffect(() => {
    const onDown = (e: KeyboardEvent) => { if (e.code === 'Space') { e.preventDefault(); setIsPanning(true); } };
    const onUp = (e: KeyboardEvent) => { if (e.code === 'Space') setIsPanning(false); };
    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    return () => { window.removeEventListener('keydown', onDown); window.removeEventListener('keyup', onUp); };
  }, []);

  const filteredAnnotations = annotations.filter((ann) => {
    if (confidenceFilter === 'all') return true;
    const tier = ann.confidence > 0.95 ? 'green' : ann.confidence >= 0.8 ? 'yellow' : 'red';
    return tier === confidenceFilter;
  });

  const cursor = isPanning ? 'grab' : canvasMode === 'draw' ? 'crosshair' : 'default';
  const zoomPct = Math.round(zoom * 100);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-gray-950">
      {/* Zoom toolbar */}
      <div className="flex items-center gap-1 px-3 py-1 bg-gray-900 border-b border-gray-700 text-xs text-gray-300">
        <button
          onClick={handleZoomOut}
          className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700"
          title="Zoom out (Ctrl+-)"
        >−</button>
        <span className="w-14 text-center font-mono">{zoomPct}%</span>
        <button
          onClick={handleZoomIn}
          className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700"
          title="Zoom in (Ctrl++)"
        >+</button>
        <button
          onClick={fitToScreen}
          className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 ml-1"
          title="Fit to screen (Ctrl+0)"
        >Fit</button>
        <button
          onClick={resetZoom}
          className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700"
          title="100% zoom"
        >1:1</button>
        <span className="ml-2 text-gray-500">Space+drag or middle-mouse to pan · Scroll to zoom</span>
      </div>

      {/* Canvas */}
      <div ref={containerRef} className="flex-1 overflow-hidden relative" style={{ cursor }}>
        <Stage
          ref={stageRef}
          width={containerSize.width}
          height={containerSize.height}
          x={stagePos.x}
          y={stagePos.y}
          scaleX={zoom}
          scaleY={zoom}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {/* Background image layer */}
          <Layer>
            {bgImage && (
              <KonvaImage
                image={bgImage}
                width={imageWidth}
                height={imageHeight}
              />
            )}
          </Layer>

          {/* Annotations layer */}
          <Layer>
            {filteredAnnotations.map((ann) => {
              const isSelected = ann.id === selectedAnnotationId;
              const strokeColor = getConfidenceColor(ann.confidence);
              const boxW = ann.x2 - ann.x1;
              const boxH = ann.y2 - ann.y1;
              return (
                <Group key={ann.id}>
                  <Rect
                    ref={isSelected ? selectedRectRef : undefined}
                    x={ann.x1}
                    y={ann.y1}
                    width={boxW}
                    height={boxH}
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 2 / zoom : 1.5 / zoom}
                    fill={isSelected ? `${strokeColor}22` : 'transparent'}
                    draggable={canvasMode === 'select' && !isLocked && !isPanning}
                    onClick={() => { if (!isLocked && !isPanning) setSelectedAnnotationId(ann.id); }}
                    onDragEnd={(e) => {
                      const node = e.target;
                      onAnnotationUpdate(ann.id, node.x(), node.y(), node.x() + boxW, node.y() + boxH);
                    }}
                    onTransformEnd={(e) => {
                      const node = e.target as Konva.Rect;
                      const sx = node.scaleX();
                      const sy = node.scaleY();
                      node.scaleX(1);
                      node.scaleY(1);
                      onAnnotationUpdate(
                        ann.id,
                        node.x(), node.y(),
                        node.x() + node.width() * sx,
                        node.y() + node.height() * sy
                      );
                    }}
                  />
                  {/* Label text on canvas */}
                  <Text
                    x={ann.x1}
                    y={Math.max(0, ann.y1 - 14 / zoom)}
                    text={ann.text || ann.label}
                    fontSize={11 / zoom}
                    fill={strokeColor}
                    listening={false}
                  />
                </Group>
              );
            })}

            {/* In-progress drawing rect */}
            {drawing && (
              <Rect
                x={drawing.w >= 0 ? drawing.x : drawing.x + drawing.w}
                y={drawing.h >= 0 ? drawing.y : drawing.y + drawing.h}
                width={Math.abs(drawing.w)}
                height={Math.abs(drawing.h)}
                stroke="#60a5fa"
                strokeWidth={1.5 / zoom}
                dash={[4 / zoom, 4 / zoom]}
                fill="rgba(96,165,250,0.1)"
                listening={false}
              />
            )}

            <Transformer
              ref={transformerRef}
              boundBoxFunc={(oldBox, newBox) => {
                if (newBox.width < 5 || newBox.height < 5) return oldBox;
                return newBox;
              }}
            />
          </Layer>
        </Stage>
      </div>
    </div>
  );
}

