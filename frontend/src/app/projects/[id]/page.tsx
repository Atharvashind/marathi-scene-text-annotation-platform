'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { fetchProjects, deleteProject } from '@/lib/api';

const ImagesTab = dynamic(() => import('./images/page'), { ssr: false });
const MetricsTab = dynamic(() => import('./metrics/page'), { ssr: false });
const ExportsTab = dynamic(() => import('./exports/page'), { ssr: false });
const SettingsTab = dynamic(() => import('./settings/page'), { ssr: false });

type Tab = 'images' | 'metrics' | 'exports' | 'settings';

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('images');

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects });
  const project = projects.find(p => p.id === id);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'images', label: 'Images' },
    { key: 'metrics', label: 'Metrics' },
    { key: 'exports', label: 'Exports' },
    { key: 'settings', label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 px-6 py-3">
        <div className="flex items-center gap-2 text-sm text-gray-400 mb-1">
          <Link href="/dashboard" className="hover:text-white">Dashboard</Link>
          <span>/</span>
          <span className="text-white">{project?.name || 'Project'}</span>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mt-2">
          {tabs.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-1.5 text-sm rounded-t transition-colors ${
                activeTab === tab.key
                  ? 'bg-gray-950 text-white border-t border-l border-r border-gray-700'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'images' && <ImagesTab />}
        {activeTab === 'metrics' && <MetricsTab />}
        {activeTab === 'exports' && <ExportsTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </div>
  );
}
