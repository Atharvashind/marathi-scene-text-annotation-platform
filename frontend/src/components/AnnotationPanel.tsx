'use client';

import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAnnotationStore } from '@/store/annotationStore';
import { getConfidenceTier } from '@/utils/confidence';
import { updateAnnotation, deleteAnnotation } from '@/lib/api';
import type { Annotation, LabelType } from '@/types';

const LABELS: LabelType[] = ['Marathi', 'English', 'Numeric', 'Mixed', 'Logo'];
const CONFIDENCE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'green', label: 'High' },
  { value: 'yellow', label: 'Medium' },
  { value: 'red', label: 'Low' },
] as const;

interface Props {
  annotations: Annotation[];
  selectedImageId: number | null;
  isLocked?: boolean;
}

export default function AnnotationPanel({ annotations, selectedImageId, isLocked = false }: Props) {
  const queryClient = useQueryClient();
  const {
    selectedAnnotationId,
    setSelectedAnnotationId,
    confidenceFilter,
    setConfidenceFilter,
  } = useAnnotationStore();

  const selected = annotations.find((a) => a.id === selectedAnnotationId) ?? null;

  const [text, setText] = useState('');
  const [label, setLabel] = useState<LabelType>('Marathi');

  useEffect(() => {
    if (selected) {
      setText(selected.text);
      setLabel(selected.label as LabelType);
    }
  }, [selected?.id]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['annotations', selectedImageId] });

  const handleTextCommit = async () => {
    if (!selected || text === selected.text) return;
    await updateAnnotation(selected.id, { text });
    invalidate();
  };

  const handleLabelChange = async (newLabel: LabelType) => {
    setLabel(newLabel);
    if (!selected) return;
    await updateAnnotation(selected.id, { label: newLabel });
    invalidate();
  };

  const handleAcceptedToggle = async () => {
    if (!selected) return;
    await updateAnnotation(selected.id, { accepted: !selected.accepted });
    invalidate();
  };

  const handleDelete = async () => {
    if (!selected) return;
    await deleteAnnotation(selected.id);
    setSelectedAnnotationId(null);
    invalidate();
  };

  const filteredAnnotations = annotations.filter((ann) => {
    if (confidenceFilter === 'all') return true;
    const tier = ann.confidence > 0.95 ? 'green' : ann.confidence >= 0.8 ? 'yellow' : 'red';
    return tier === confidenceFilter;
  });

  return (
    <aside className="w-72 bg-gray-900 border-l border-gray-700 flex flex-col overflow-hidden">
      {/* Confidence filter */}
      <div className="p-3 border-b border-gray-700">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">
          Confidence Filter
        </p>
        <div className="flex gap-1 flex-wrap">
          {CONFIDENCE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setConfidenceFilter(f.value)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                confidenceFilter === f.value
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Annotation list */}
      <div className="flex-1 overflow-y-auto">
        {filteredAnnotations.length === 0 ? (
          <p className="p-4 text-sm text-gray-500 text-center">No annotations</p>
        ) : (
          <ul className="divide-y divide-gray-800">
            {filteredAnnotations.map((ann) => {
              const tier = getConfidenceTier(ann.confidence);
              const isSelected = ann.id === selectedAnnotationId;
              return (
                <li key={ann.id}>
                  <button
                    onClick={() => setSelectedAnnotationId(ann.id)}
                    className={`w-full text-left p-2 hover:bg-gray-800 transition-colors ${
                      isSelected ? 'bg-gray-800 border-l-2 border-blue-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs text-gray-200 truncate flex-1">
                        {ann.text || <span className="italic text-gray-500">empty</span>}
                      </span>
                      <span
                        className={`text-[10px] px-1 py-0.5 rounded border ${tier.tailwind}`}
                        title={tier.label}
                      >
                        {ann.confidence.toFixed(2)}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-500">{ann.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Selected annotation editor */}
      {selected && (
        <div className="border-t border-gray-700 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Edit Annotation
            </h3>
            <button
              onClick={handleDelete}
              disabled={isLocked}
              className="text-xs text-red-400 hover:text-red-300 disabled:opacity-40"
            >
              Delete
            </button>
          </div>

          {/* Confidence badge */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Confidence</span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded border ${getConfidenceTier(selected.confidence).tailwind}`}
            >
              {selected.confidence.toFixed(2)}
            </span>
          </div>

          {/* Text */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Text</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onBlur={handleTextCommit}
              disabled={isLocked}
              rows={2}
              className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 resize-none focus:outline-none focus:border-blue-500 disabled:opacity-40"
            />
          </div>

          {/* Label */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Label</label>
            <select
              value={label}
              onChange={(e) => handleLabelChange(e.target.value as LabelType)}
              disabled={isLocked}
              className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500 disabled:opacity-40"
            >
              {LABELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {/* Accepted toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="accepted"
              checked={selected.accepted}
              onChange={handleAcceptedToggle}
              disabled={isLocked}
              className="accent-green-500 disabled:opacity-40"
            />
            <label htmlFor="accepted" className="text-xs text-gray-300">
              Accepted
            </label>
            {selected.is_corrected && (
              <span className="ml-auto text-[10px] text-orange-400 border border-orange-700 rounded px-1">
                Corrected
              </span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
