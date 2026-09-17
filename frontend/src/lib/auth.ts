import type { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });
          if (!res.ok) return null;
          const data = await res.json();
          // Fetch user profile
          const profileRes = await fetch(`${API_BASE}/users/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
          });
          const profile = profileRes.ok ? await profileRes.json() : {};
          return {
            id: profile.id || '',
            name: profile.name || credentials.email,
            email: profile.email || credentials.email,
            role: profile.role || 'annotator',
            accessToken: data.access_token,
          };
        } catch {
          return null;
        }
      },
    }),
    // Google OAuth — enabled when GOOGLE_CLIENT_ID env var is set
    ...(process.env.GOOGLE_CLIENT_ID
      ? [
          // Dynamic import to avoid errors when not configured
          // GoogleProvider({ clientId: process.env.GOOGLE_CLIENT_ID!, clientSecret: process.env.GOOGLE_CLIENT_SECRET! })
        ]
      : []),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as any).accessToken;
        token.role = (user as any).role;
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).role = token.role;
      if (session.user) {
        session.user.name = token.name || session.user.name;
        (session.user as any).id = token.id;
      }
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  session: { strategy: 'jwt' },
  secret: process.env.NEXTAUTH_SECRET,
};
