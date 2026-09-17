'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { downloadExport } from '@/lib/api';
import type { ExportFormat } from '@/types';

const FORMATS: { fmt: ExportFormat; label: string; desc: string }[] = [
  { fmt: 'yolo', label: 'YOLO', desc: 'class_id x_center y_center width height' },
  { fmt: 'coco', label: 'COCO JSON', desc: 'Standard COCO annotation format' },
  { fmt: 'labelstudio', label: 'Label Studio', desc: 'RectangleLabels import format' },
  { fmt: 'custom_json', label: 'Custom JSON', desc: 'All annotation fields (round-trip)' },
];

export default function ExportsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const [loading, setLoading] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const [approvedOnly, setApprovedOnly] = useState(false);

  const handleExport = async (fmt: ExportFormat) => {
    setLoading(fmt);
    try {
      await downloadExport(projectId, 'all', fmt, approvedOnly ? 'Approved' : undefined);
    } catch (err: any) {
      setToast(`Export failed: ${err.message}`);
      setTimeout(() => setToast(''), 3000);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <h2 className="text-base font-semibold text-white mb-4">Export Annotations</h2>

      <label className="flex items-center gap-2 text-sm text-gray-300 mb-6 cursor-pointer">
        <input type="checkbox" checked={approvedOnly} onChange={e => setApprovedOnly(e.target.checked)}
          className="accent-green-500" />
        Export Approved images only
      </label>

      <div className="space-y-3">
        {FORMATS.map(({ fmt, label, desc }) => (
          <div key={fmt} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
            <div>
              <p className="text-sm font-medium text-white">{label}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
            <button onClick={() => handleExport(fmt)} disabled={loading === fmt}
              className="px-3 py-1.5 text-xs bg-orange-700 hover:bg-orange-600 text-white rounded disabled:opacity-50">
              {loading === fmt ? 'Downloading…' : 'Download'}
            </button>
          </div>
        ))}
      </div>

      {toast && (
        <div className="fixed bottom-4 right-4 bg-red-700 text-white text-sm px-4 py-2 rounded shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
