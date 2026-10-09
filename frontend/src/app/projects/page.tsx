'use client';

import { useState, useEffect } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API = 'http://localhost:8000';

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  image_count: number;
  status: string;
}

async function fetchProjects(): Promise<Project[]> {
  const r = await fetch(`${API}/api/projects`);
  if (!r.ok) throw new Error('Failed to fetch projects');
  return r.json();
}

async function createProject(name: string, description: string): Promise<Project> {
  const r = await fetch(`${API}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!r.ok) throw new Error('Failed to create project');
  return r.json();
}

export default function ProjectsPage() {
  const { data: session, status } = useSession();
  const router  = useRouter();
  const qc      = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [name,       setName]       = useState('');
  const [desc,       setDesc]       = useState('');
  const [creating,   setCreating]   = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login?callbackUrl=/projects');
    }
  }, [status, router]);

  const { data: projects = [], isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
    enabled: status === 'authenticated',
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createProject(name.trim(), desc.trim());
      setName(''); setDesc(''); setShowCreate(false);
      qc.invalidateQueries({ queryKey: ['projects'] });
    } catch (err) {
      alert(`Failed: ${err}`);
    } finally {
      setCreating(false);
    }
  };

  // Loading state while checking session
  if (status === 'loading' || status === 'unauthenticated') {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Loading…</p>
        </div>
      </div>
    );
  }

  const userName  = session?.user?.name || session?.user?.email || 'User';
  const userEmail = session?.user?.email || '';
  const initials  = userName.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* Navbar */}
      <nav className="h-14 bg-gray-900 border-b border-gray-700 flex items-center px-6 gap-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-xs font-bold">म</div>
          <span className="font-semibold text-white">Marathi Scene Text Annotation</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* User badge */}
          <div className="flex items-center gap-2 text-sm text-gray-300">
            <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-semibold">
              {initials}
            </div>
            <span className="hidden sm:inline text-gray-400">{userEmail}</span>
          </div>

          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="text-xs text-gray-400 hover:text-white px-2.5 py-1 rounded hover:bg-gray-800 transition">
            Sign out
          </button>

          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg font-medium transition">
            + New Project
          </button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold">Projects</h1>
          <p className="text-sm text-gray-400 mt-0.5">Create and manage Marathi scene-text annotation projects</p>
        </div>

        {/* Loading skeletons */}
        {isLoading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-gray-900 border border-gray-700 rounded-xl p-5 animate-pulse h-32" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm px-4 py-3 rounded-lg">
            Cannot reach backend at {API}. Make sure the backend is running.
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && projects.length === 0 && (
          <div className="text-center py-24">
            <div className="text-6xl mb-4">📁</div>
            <p className="text-gray-300 font-medium mb-1">No projects yet</p>
            <p className="text-gray-500 text-sm mb-6">Create your first annotation project to get started</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg font-medium transition">
              + New Project
            </button>
          </div>
        )}

        {/* Project grid */}
        {projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map(p => (
              <Link
                key={p.id}
                href={`/projects/${p.id}/images`}
                className="block bg-gray-900 border border-gray-700 rounded-xl p-5 hover:border-blue-500/60
                           hover:bg-gray-800/60 transition-all group">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-white group-hover:text-blue-400 transition-colors leading-tight">
                    {p.name}
                  </h3>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded capitalize ml-2 shrink-0 ${
                    p.status === 'active' ? 'bg-green-900/60 text-green-300' : 'bg-gray-700 text-gray-400'
                  }`}>
                    {p.status}
                  </span>
                </div>
                <p className="text-sm text-gray-400 line-clamp-2 mb-4 min-h-[2.5rem]">
                  {p.description || 'No description'}
                </p>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>{p.image_count} image{p.image_count !== 1 ? 's' : ''}</span>
                  <span className="text-gray-600">
                    {new Date(p.created_at).toLocaleDateString()}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreate && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => setShowCreate(false)}>
          <div
            className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl"
            onClick={e => e.stopPropagation()}>

            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">New Project</h2>
              <button
                onClick={() => setShowCreate(false)}
                className="text-gray-500 hover:text-white text-xl w-7 h-7 flex items-center justify-center rounded hover:bg-gray-700 transition">
                ×
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Project name *</label>
                <input
                  type="text" value={name} onChange={e => setName(e.target.value)}
                  required autoFocus
                  className="w-full px-3 py-2.5 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm
                             placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                  placeholder="e.g. Pune Signboards Batch 1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
                <textarea
                  value={desc} onChange={e => setDesc(e.target.value)} rows={3}
                  className="w-full px-3 py-2.5 bg-gray-800 border border-gray-600 rounded-lg text-white text-sm
                             placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition resize-none"
                  placeholder="Optional description…"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="button" onClick={() => setShowCreate(false)}
                  className="flex-1 px-4 py-2.5 border border-gray-600 text-gray-400 rounded-lg hover:bg-gray-800 text-sm transition">
                  Cancel
                </button>
                <button
                  type="submit" disabled={creating || !name.trim()}
                  className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold
                             disabled:opacity-50 disabled:cursor-not-allowed transition">
                  {creating ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Creating…
                    </span>
                  ) : 'Create project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
