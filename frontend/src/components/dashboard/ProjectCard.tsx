'use client';

import Link from 'next/link';
import type { Project } from '@/lib/api';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.id}`}
      className="block bg-gray-900 border border-gray-700 rounded-lg p-4 hover:border-blue-500 hover:bg-gray-800 transition-colors">
      <h3 className="text-white font-semibold truncate mb-1">{project.name}</h3>
      {project.description && (
        <p className="text-gray-400 text-xs truncate mb-3">{project.description}</p>
      )}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>{project.image_count} images</span>
        <span className="text-green-400">{project.approved_count} approved</span>
        <span className="ml-auto">{timeAgo(project.updated_at)}</span>
      </div>
    </Link>
  );
}
