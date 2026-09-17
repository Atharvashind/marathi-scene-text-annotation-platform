'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { signOut, useSession } from 'next-auth/react';
import Link from 'next/link';
import { fetchProjects } from '@/lib/api';
import ProjectCard from '@/components/dashboard/ProjectCard';
import CreateProjectModal from '@/components/dashboard/CreateProjectModal';

export default function DashboardPage() {
  const { data: session } = useSession();
  const [showCreate, setShowCreate] = useState(false);

  const { data: projects = [], isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  });

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Navbar */}
      <nav className="h-14 bg-gray-900 border-b border-gray-700 flex items-center px-6 gap-4">
        <span className="font-semibold text-white">Marathi Annotation</span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm text-gray-400">{session?.user?.name || session?.user?.email}</span>
          <Link href="/settings" className="text-xs text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-800">
            Settings
          </Link>
          <button onClick={() => signOut({ callbackUrl: '/login' })}
            className="text-xs text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-800">
            Logout
          </button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold">My Projects</h1>
          <button onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded font-medium">
            + New Project
          </button>
        </div>

        {isLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-gray-900 border border-gray-700 rounded-lg p-4 animate-pulse h-28" />
            ))}
          </div>
        )}

        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm px-4 py-3 rounded">
            Failed to load projects. Please refresh.
          </div>
        )}

        {!isLoading && projects.length === 0 && (
          <div className="text-center py-20">
            <p className="text-4xl mb-4">📁</p>
            <p className="text-gray-400 mb-4">No projects yet.</p>
            <button onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded">
              Create your first project
            </button>
          </div>
        )}

        {projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map(p => <ProjectCard key={p.id} project={p} />)}
          </div>
        )}
      </div>

      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
