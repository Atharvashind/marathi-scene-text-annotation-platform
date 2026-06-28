'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Transformer, Text } from 'react-konva';
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
  const [stageSize, setStageSize] = useState({ width: 800, height: 600 });
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const [drawing, setDrawing] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const transformerRef = useRef<Konva.Transformer>(null);
  const selectedRectRef = useRef<Konva.Rect>(null);

  const { canvasMode, selectedAnnotationId, setSelectedAnnotationId, confidenceFilter } =
    useAnnotationStore();

  // Load background image
  useEffect(() => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.src = imageUrl;
    img.onload = () => setBgImage(img);
  }, [imageUrl]);

  // Resize observer — fit image inside container preserving aspect ratio
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const imageRatio = imageHeight / imageWidth;
      const containerRatio = height / width;

      let stageWidth: number;
      let stageHeight: number;

      if (imageRatio > containerRatio) {
        // Image is taller relative to container — fit by height
        stageHeight = height;
        stageWidth = height / imageRatio;
      } else {
        // Image is wider relative to container — fit by width
        stageWidth = width;
        stageHeight = width * imageRatio;
      }

      setStageSize({ width: stageWidth, height: stageHeight });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, [imageWidth, imageHeight]);

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

  // Delete key handler
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAnnotationId !== null) {
        onAnnotationDelete(selectedAnnotationId);
        setSelectedAnnotationId(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedAnnotationId, onAnnotationDelete, setSelectedAnnotationId]);

  const scale = stageSize.width / imageWidth;

  const filteredAnnotations = annotations.filter((ann) => {
    if (confidenceFilter === 'all') return true;
    const tier =
      ann.confidence > 0.95 ? 'green' : ann.confidence >= 0.8 ? 'yellow' : 'red';
    return tier === confidenceFilter;
  });

  const handleStageMouseDown = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (isLocked) return;
      if (canvasMode !== 'draw') {
        // Deselect when clicking stage background
        if (e.target === e.target.getStage()) {
          setSelectedAnnotationId(null);
        }
        return;
      }
      const stage = e.target.getStage();
      if (!stage) return;
      const pos = stage.getPointerPosition();
      if (!pos) return;
      setDrawing({ x: pos.x / scale, y: pos.y / scale, w: 0, h: 0 });
    },
    [canvasMode, scale, setSelectedAnnotationId, isLocked]
  );

  const handleStageMouseMove = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (!drawing) return;
      const stage = e.target.getStage();
      if (!stage) return;
      const pos = stage.getPointerPosition();
      if (!pos) return;
      setDrawing((d) =>
        d ? { ...d, w: pos.x / scale - d.x, h: pos.y / scale - d.y } : null
      );
    },
    [drawing, scale]
  );

  const handleStageMouseUp = useCallback(() => {
    if (!drawing) return;
    const minSize = 5;
    if (Math.abs(drawing.w) > minSize && Math.abs(drawing.h) > minSize) {
      const x1 = drawing.w >= 0 ? drawing.x : drawing.x + drawing.w;
      const y1 = drawing.h >= 0 ? drawing.y : drawing.y + drawing.h;
      onAnnotationCreate({
        x1,
        y1,
        x2: x1 + Math.abs(drawing.w),
        y2: y1 + Math.abs(drawing.h),
      });
    }
    setDrawing(null);
  }, [drawing, onAnnotationCreate]);

  return (
    <div ref={containerRef} className="flex-1 overflow-auto bg-gray-950 relative flex items-start justify-center">
      <Stage
        width={stageSize.width}
        height={stageSize.height}
        onMouseDown={handleStageMouseDown}
        onMouseMove={handleStageMouseMove}
        onMouseUp={handleStageMouseUp}
        style={{ cursor: canvasMode === 'draw' ? 'crosshair' : 'default' }}
      >
        {/* Background image layer */}
        <Layer>
          {bgImage && (
            <KonvaImage
              image={bgImage}
              width={stageSize.width}
              height={stageSize.height}
            />
          )}
        </Layer>

        {/* Annotations layer */}
        <Layer>
          {filteredAnnotations.map((ann) => {
            const isSelected = ann.id === selectedAnnotationId;
            const strokeColor = getConfidenceColor(ann.confidence);
            return (
              <Rect
                key={ann.id}
                ref={isSelected ? selectedRectRef : undefined}
                x={ann.x1 * scale}
                y={ann.y1 * scale}
                width={(ann.x2 - ann.x1) * scale}
                height={(ann.y2 - ann.y1) * scale}
                stroke={strokeColor}
                strokeWidth={isSelected ? 2 : 1.5}
                fill={isSelected ? `${strokeColor}22` : 'transparent'}
                draggable={canvasMode === 'select' && !isLocked}
                onClick={() => {
                  if (!isLocked) setSelectedAnnotationId(ann.id);
                }}
                onDragEnd={(e) => {
                  const node = e.target;
                  const newX1 = node.x() / scale;
                  const newY1 = node.y() / scale;
                  const w = (ann.x2 - ann.x1);
                  const h = (ann.y2 - ann.y1);
                  onAnnotationUpdate(ann.id, newX1, newY1, newX1 + w, newY1 + h);
                }}
                onTransformEnd={(e) => {
                  const node = e.target as Konva.Rect;
                  const scaleX = node.scaleX();
                  const scaleY = node.scaleY();
                  node.scaleX(1);
                  node.scaleY(1);
                  const newX1 = node.x() / scale;
                  const newY1 = node.y() / scale;
                  const newX2 = newX1 + (node.width() * scaleX) / scale;
                  const newY2 = newY1 + (node.height() * scaleY) / scale;
                  onAnnotationUpdate(ann.id, newX1, newY1, newX2, newY2);
                }}
              />
            );
          })}

          {/* In-progress drawing rect */}
          {drawing && (
            <Rect
              x={(drawing.w >= 0 ? drawing.x : drawing.x + drawing.w) * scale}
              y={(drawing.h >= 0 ? drawing.y : drawing.y + drawing.h) * scale}
              width={Math.abs(drawing.w) * scale}
              height={Math.abs(drawing.h) * scale}
              stroke="#60a5fa"
              strokeWidth={1.5}
              dash={[4, 4]}
              fill="rgba(96,165,250,0.1)"
              listening={false}
            />
          )}

          {/* Transformer for resize handles */}
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
  );
}
