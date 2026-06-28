'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchImageMetrics, fetchProjectMetrics } from '@/lib/api';

interface Props {
  imageId: number | null;
  onClose: () => void;
}

function Metric({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="bg-gray-800 rounded p-3">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-lg font-semibold text-white">
        {value === null || value === undefined ? '—' : value}
      </p>
    </div>
  );
}

function pct(v: number | null) {
  if (v === null) return null;
  return `${(v * 100).toFixed(1)}%`;
}

function secs(v: number | null) {
  if (v === null) return null;
  return `${v.toFixed(0)}s`;
}

export default function StatsDashboard({ imageId, onClose }: Props) {
  const { data: projectMetrics } = useQuery({
    queryKey: ['metrics', 'project'],
    queryFn: fetchProjectMetrics,
  });

  const { data: imageMetrics } = useQuery({
    queryKey: ['metrics', 'image', imageId],
    queryFn: () => fetchImageMetrics(imageId!),
    enabled: imageId !== null,
  });

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-base font-semibold text-white">Annotation Statistics</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Project-level */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
              Project Level
            </h3>
            {projectMetrics ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <Metric label="Total Images" value={projectMetrics.total_images} />
                <Metric label="Total Annotations" value={projectMetrics.total_annotations} />
                <Metric
                  label="Avg Confidence"
                  value={
                    projectMetrics.average_confidence !== null
                      ? projectMetrics.average_confidence.toFixed(2)
                      : null
                  }
                />
                <Metric label="Mean TSE" value={secs(projectMetrics.mean_tse)} />
                <Metric label="Mean AAR" value={pct(projectMetrics.mean_aar)} />
                <Metric label="Mean BCR" value={pct(projectMetrics.mean_bcr)} />
                <Metric label="Mean MAR" value={pct(projectMetrics.mean_mar)} />
              </div>
            ) : (
              <p className="text-sm text-gray-500">Loading…</p>
            )}
          </section>

          {/* Per-image */}
          {imageId && (
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                Current Image
              </h3>
              {imageMetrics ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <Metric label="Total OCR" value={imageMetrics.total_ocr} />
                  <Metric label="Total Annotations" value={imageMetrics.total_annotations} />
                  <Metric label="High Confidence" value={imageMetrics.high_confidence_count} />
                  <Metric label="Low Confidence" value={imageMetrics.low_confidence_count} />
                  <Metric label="AAR" value={pct(imageMetrics.aar)} />
                  <Metric label="BCR" value={pct(imageMetrics.bcr)} />
                  <Metric label="MAR" value={pct(imageMetrics.mar)} />
                  <Metric label="Time Saved" value={secs(imageMetrics.tse)} />
                </div>
              ) : (
                <p className="text-sm text-gray-500">Loading…</p>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
