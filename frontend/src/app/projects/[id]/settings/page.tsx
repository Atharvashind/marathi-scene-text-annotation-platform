'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchProjects, updateProject, deleteProject } from '@/lib/api';

export default function ProjectSettingsPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: fetchProjects });
  const project = projects.find(p => p.id === projectId);

  const [name, setName] = useState(project?.name || '');
  const [description, setDescription] = useState(project?.description || '');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [toast, setToast] = useState('');

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 3000); };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProject(projectId, { name, description });
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      showToast('Project updated');
    } catch {
      showToast('Failed to update project');
    } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteProject(projectId);
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      router.push('/dashboard');
    } catch {
      showToast('Failed to delete project');
      setDeleting(false);
    }
  };

  return (
    <div className="p-6 max-w-lg">
      <h2 className="text-base font-semibold text-white mb-6">Project Settings</h2>

      <form onSubmit={handleSave} className="space-y-4 mb-8">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Project name</label>
          <input value={name} onChange={e => setName(e.target.value)} maxLength={100} required
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Description</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2}
            className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-blue-500" />
        </div>
        <button type="submit" disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded disabled:opacity-50">
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </form>

      <div className="border-t border-red-900/50 pt-6">
        <h3 className="text-sm font-semibold text-red-400 mb-2">Danger Zone</h3>
        <p className="text-xs text-gray-400 mb-3">Deleting a project permanently removes all images and annotations.</p>
        {!confirmDelete ? (
          <button onClick={() => setConfirmDelete(true)}
            className="px-4 py-2 bg-red-900/40 border border-red-700 text-red-400 hover:bg-red-800 text-sm rounded">
            Delete Project
          </button>
        ) : (
          <div className="flex gap-2">
            <button onClick={handleDelete} disabled={deleting}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white text-sm rounded disabled:opacity-50">
              {deleting ? 'Deleting…' : 'Confirm Delete'}
            </button>
            <button onClick={() => setConfirmDelete(false)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded">
              Cancel
            </button>
          </div>
        )}
      </div>

      {toast && (
        <div className="fixed bottom-4 right-4 bg-gray-700 text-white text-sm px-4 py-2 rounded shadow-lg">{toast}</div>
      )}
    </div>
  );
}
