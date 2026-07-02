'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { fetchProjectMetrics } from '@/lib/api';

function Metric({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="bg-gray-800 rounded p-3">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-lg font-semibold text-white">{value === null || value === undefined ? '—' : value}</p>
    </div>
  );
}

function pct(v: number | null) { return v === null ? null : `${(v * 100).toFixed(1)}%`; }
function secs(v: number | null) { return v === null ? null : `${v.toFixed(0)}s`; }

export default function MetricsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const { data: m, isLoading } = useQuery({
    queryKey: ['metrics', 'project', projectId],
    queryFn: () => fetchProjectMetrics(projectId),
  });

  if (isLoading) return <div className="p-6 text-gray-400 text-sm">Loading metrics…</div>;

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-base font-semibold text-white mb-4">Project Metrics</h2>
      {m ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Metric label="Total Images" value={m.total_images} />
          <Metric label="Total Annotations" value={m.total_annotations} />
          <Metric label="Avg Confidence" value={m.average_confidence ? m.average_confidence.toFixed(2) : null} />
          <Metric label="Mean TSE" value={secs(m.mean_tse)} />
          <Metric label="Mean AAR" value={pct(m.mean_aar)} />
          <Metric label="Mean BCR" value={pct(m.mean_bcr)} />
          <Metric label="Mean MAR" value={pct(m.mean_mar)} />
        </div>
      ) : (
        <p className="text-gray-500 text-sm">No metrics available yet. Upload and annotate images first.</p>
      )}
    </div>
  );
}
