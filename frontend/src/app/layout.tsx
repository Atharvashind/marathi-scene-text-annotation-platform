import type { Metadata } from 'next';
import '../styles/globals.css';
import { SessionProvider } from '@/providers/SessionProvider';
import { QueryProvider } from '@/providers/QueryProvider';

export const metadata: Metadata = {
  title: 'Marathi Scene Text Annotation Platform',
  description: 'Human-in-the-Loop OCR annotation tool for Marathi scene text datasets',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white">
        <SessionProvider>
          <QueryProvider>
            {children}
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
