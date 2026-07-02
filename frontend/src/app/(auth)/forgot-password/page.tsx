'use client';

import { useState } from 'react';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-white text-center mb-2">Reset password</h1>

        {submitted ? (
          <div className="text-center space-y-4">
            <div className="bg-green-900/40 border border-green-700 text-green-300 text-sm px-3 py-3 rounded">
              If that email is registered, a reset link will be sent. (Password reset is coming soon.)
            </div>
            <Link href="/login" className="text-blue-400 hover:text-blue-300 text-sm">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 mt-6">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                placeholder="you@example.com" />
            </div>
            <button type="submit"
              className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded py-2 text-sm font-medium">
              Send reset link
            </button>
            <p className="text-center">
              <Link href="/login" className="text-sm text-gray-400 hover:text-gray-300">
                Back to sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
