'use client';
/**
 * AnnotationCanvas — Konva drawing surface.
 * Imported with dynamic({ ssr: false }) from the annotate page.
 *
 * Box interaction model:
 *   Select mode  → click to select, drag to MOVE, wheel to zoom, middle-drag to pan
 *   Draw mode    → drag to draw new box, click elsewhere does nothing
 */
import React, { useState } from 'react';
import { Stage, Layer, Image as KonvaImage, Rect, Text, Group } from 'react-konva';
import { labelColor, type Annotation } from '@/lib/annotation-types';
export type { Annotation };

interface DrawBox { x: number; y: number; w: number; h: number; }

interface Props {
  width:       number;
  height:      number;
  imgEl:       HTMLImageElement | null;
  scale:       number;
  offset:      { x: number; y: number };
  annotations: Annotation[];
  selectedId:  string | null;
  drawing:     DrawBox | null;
  mode:        'select' | 'draw';
  stageRef:    React.RefObject<any>;
  onMouseDown: (e: any) => void;
  onMouseMove: (e: any) => void;
  onMouseUp:   ()      => void;
  onWheel:     (e: any) => void;
  onSelect:    (ann: Annotation) => void;
  onDeselect:  () => void;
  /** Called with new image-coordinate bbox after a drag completes */
  onBoxMoved:  (id: string, x1: number, y1: number, x2: number, y2: number) => void;
}

export default function AnnotationCanvas({
  width, height, imgEl, scale, offset,
  annotations, selectedId, drawing, mode,
  stageRef, onMouseDown, onMouseMove, onMouseUp, onWheel,
  onSelect, onDeselect, onBoxMoved,
}: Props) {
  // Track which box is mid-drag so we can show it at its new position
  // before the server round-trip completes.
  const [dragPos, setDragPos] = useState<Record<string, { x: number; y: number }>>({});

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onWheel={onWheel}
    >
      <Layer>
        {/* Single Group — handles pan (x/y) + zoom (scaleX/scaleY) */}
        <Group x={offset.x} y={offset.y} scaleX={scale} scaleY={scale}>

          {/* Base image — with shadow + border frame */}
          {imgEl && (
            <>
              {/* Drop-shadow behind the image */}
              <Rect
                x={-1 / scale}
                y={-1 / scale}
                width={imgEl.naturalWidth  + 2 / scale}
                height={imgEl.naturalHeight + 2 / scale}
                fill="#0f172a"
                stroke="#334155"
                strokeWidth={1 / scale}
                shadowColor="rgba(0,0,0,0.7)"
                shadowBlur={24 / scale}
                shadowOffsetX={0}
                shadowOffsetY={6 / scale}
                shadowEnabled
                cornerRadius={2 / scale}
                listening={false}
              />
              <KonvaImage
                image={imgEl}
                width={imgEl.naturalWidth}
                height={imgEl.naturalHeight}
                onClick={() => { if (mode === 'select') onDeselect(); }}
              />
              {/* Thin inset highlight on top edge */}
              <Rect
                x={0}
                y={0}
                width={imgEl.naturalWidth}
                height={imgEl.naturalHeight}
                fill="transparent"
                stroke="rgba(255,255,255,0.08)"
                strokeWidth={1 / scale}
                listening={false}
              />
            </>
          )}

          {/* Annotation boxes */}
          {annotations.map((ann) => {
            const isSelected = ann.id === selectedId;
            const color      = labelColor(ann.label);
            const sw         = (isSelected ? 2.5 : 1.5) / scale;
            const bw         = ann.x2 - ann.x1;
            const bh         = ann.y2 - ann.y1;
            const tagH       = 17 / scale;
            const tagW       = Math.max((ann.text?.length || 4) * 7 / scale, 28 / scale);
            const fontSize   = 10 / scale;

            // Use live drag position if this box is being dragged
            const dp  = dragPos[ann.id];
            const bx  = dp ? dp.x : ann.x1;
            const by  = dp ? dp.y : ann.y1;

            return (
              <React.Fragment key={ann.id}>
                {/* ── Bounding box (draggable in select mode) ── */}
                <Rect
                  x={bx} y={by}
                  width={bw} height={bh}
                  stroke={isSelected ? '#FFFFFF' : color}
                  strokeWidth={sw}
                  fill={isSelected ? 'rgba(255,255,255,0.08)' : `${color}22`}
                  shadowColor={isSelected ? '#FFFFFF' : undefined}
                  shadowBlur={isSelected ? 6 / scale : 0}
                  listening={mode === 'select'}
                  // Dragging only active in select mode
                  draggable={mode === 'select'}
                  // Show move cursor when hoverable
                  onMouseEnter={e => {
                    if (mode !== 'select') return;
                    const stage = e.target.getStage();
                    if (stage) stage.container().style.cursor = 'move';
                  }}
                  onMouseLeave={e => {
                    const stage = e.target.getStage();
                    if (stage) stage.container().style.cursor = '';
                  }}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    onSelect(ann);
                  }}
                  onDragStart={(e) => {
                    e.cancelBubble = true;  // don't trigger pan
                    onSelect(ann);
                    setDragPos(prev => ({ ...prev, [ann.id]: { x: e.target.x(), y: e.target.y() } }));
                  }}
                  onDragMove={(e) => {
                    setDragPos(prev => ({ ...prev, [ann.id]: { x: e.target.x(), y: e.target.y() } }));
                  }}
                  onDragEnd={(e) => {
                    const newX = e.target.x();
                    const newY = e.target.y();
                    // Reset Konva's internal position — we manage coords ourselves
                    e.target.x(ann.x1);
                    e.target.y(ann.y1);
                    setDragPos(prev => {
                      const next = { ...prev };
                      delete next[ann.id];
                      return next;
                    });
                    // Calculate how far we moved
                    const dx = newX - ann.x1;
                    const dy = newY - ann.y1;
                    // Clamp so box can't be dragged off the image
                    const imgW = imgEl?.naturalWidth  ?? 99999;
                    const imgH = imgEl?.naturalHeight ?? 99999;
                    const clampedX1 = Math.max(0, Math.min(ann.x1 + dx, imgW  - bw));
                    const clampedY1 = Math.max(0, Math.min(ann.y1 + dy, imgH  - bh));
                    onBoxMoved(ann.id, clampedX1, clampedY1, clampedX1 + bw, clampedY1 + bh);
                  }}
                />

                {/* ── Label tag — follows box during drag ── */}
                <Rect
                  x={bx}
                  y={by - tagH - 1 / scale}
                  width={tagW}
                  height={tagH}
                  fill={color}
                  cornerRadius={2 / scale}
                  listening={false}
                />
                <Text
                  x={bx + 2 / scale}
                  y={by - tagH + 2 / scale}
                  text={ann.text ? ann.text.slice(0, 22) : ann.label}
                  fontSize={fontSize}
                  fill="#FFFFFF"
                  listening={false}
                />
              </React.Fragment>
            );
          })}

          {/* ── Live drawing rect ── */}
          {drawing && (
            <Rect
              x={drawing.w >= 0 ? drawing.x : drawing.x + drawing.w}
              y={drawing.h >= 0 ? drawing.y : drawing.y + drawing.h}
              width={Math.abs(drawing.w)}
              height={Math.abs(drawing.h)}
              stroke="#60A5FA"
              strokeWidth={1.5 / scale}
              fill="rgba(96,165,250,0.15)"
              dash={[6 / scale, 3 / scale]}
              listening={false}
            />
          )}

        </Group>
      </Layer>
    </Stage>
  );
}
