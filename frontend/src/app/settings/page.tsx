'use client';

import { useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function SettingsPage() {
  const { data: session, update } = useSession();
  const [name, setName] = useState(session?.user?.name || '');
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [saving, setSaving] = useState(false);
  const [savingPw, setSavingPw] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const getToken = () => (session as any)?.accessToken || '';

  const handleNameSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error(await res.text());
      await update({ name });
      showToast('Name updated');
    } catch { showToast('Failed to update name', 'error'); } finally { setSaving(false); }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw.length < 8) { showToast('Password must be at least 8 characters', 'error'); return; }
    setSavingPw(true);
    try {
      const res = await fetch(`${API_BASE}/users/me/password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed');
      }
      setCurrentPw(''); setNewPw('');
      showToast('Password changed');
    } catch (err: any) { showToast(err.message || 'Failed to change password', 'error'); }
    finally { setSavingPw(false); }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="h-14 bg-gray-900 border-b border-gray-700 flex items-center px-6 gap-4">
        <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm">← Dashboard</Link>
        <span className="text-white font-semibold ml-2">Account Settings</span>
      </nav>

      <div className="max-w-lg mx-auto px-6 py-8 space-y-8">
        {/* Profile info */}
        <section className="bg-gray-900 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Profile</h2>
          <div className="space-y-2 text-sm mb-4">
            <div className="flex gap-2"><span className="text-gray-400 w-24">Email</span><span className="text-white">{session?.user?.email}</span></div>
            <div className="flex gap-2"><span className="text-gray-400 w-24">Role</span><span className="text-white capitalize">{(session as any)?.role || 'annotator'}</span></div>
          </div>
          <form onSubmit={handleNameSave} className="flex gap-2">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Display name"
              className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500" />
            <button type="submit" disabled={saving}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded disabled:opacity-50">
              {saving ? 'Saving…' : 'Save'}
            </button>
          </form>
        </section>

        {/* Change password */}
        <section className="bg-gray-900 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Change Password</h2>
          <form onSubmit={handlePasswordChange} className="space-y-3">
            <input type="password" value={currentPw} onChange={e => setCurrentPw(e.target.value)}
              placeholder="Current password" required
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
              placeholder="New password (min 8 chars)" required
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            <button type="submit" disabled={savingPw}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded disabled:opacity-50">
              {savingPw ? 'Changing…' : 'Change Password'}
            </button>
          </form>
        </section>

        {/* Account actions */}
        <section className="bg-gray-900 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Account</h2>
          <div className="space-y-3">
            <button onClick={() => signOut({ callbackUrl: '/login' })}
              className="w-full px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded text-left">
              Logout
            </button>
            <button disabled title="Coming soon"
              className="w-full px-4 py-2 bg-red-900/30 border border-red-800 text-red-400 text-sm rounded text-left opacity-50 cursor-not-allowed">
              Delete Account (coming soon)
            </button>
          </div>
        </section>
      </div>

      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded shadow-lg text-sm text-white z-50 ${
          toast.type === 'success' ? 'bg-green-700' : 'bg-red-700'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
