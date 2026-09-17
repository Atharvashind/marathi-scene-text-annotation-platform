import type { AppProps } from 'next/app';
import { QueryProvider } from '@/providers/QueryProvider';
import '../styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <QueryProvider>
      <Component {...pageProps} />
    </QueryProvider>
  );
}
