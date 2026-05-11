'use client';

import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiError } from '@/lib/api/client';

/**
 * App-wide TanStack Query client.
 *
 *  - `staleTime: 60_000`: dedupes in-flight + parallel renders for a minute.
 *  - `refetchOnWindowFocus: false`: workspace data is heavy; don't churn on tab switches.
 *  - Skips retry on auth errors (401/403); `authFetch` already handles refresh.
 *  - Listens for the legacy `graph-cache-refresh` window event so existing code
 *    paths that dispatch it (e.g. agent tools / bulk operations elsewhere in the
 *    app) keep invalidating the right keys without coupling.
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            gcTime: 10 * 60_000,
            refetchOnWindowFocus: false,
            retry: (failureCount, error) => {
              if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
                return false;
              }
              return failureCount < 2;
            },
          },
          mutations: {
            retry: false,
          },
        },
      }),
  );

  useEffect(() => {
    const onRefresh = () => {
      void client.invalidateQueries({ queryKey: ['graph'] });
      void client.invalidateQueries({ queryKey: ['ontology'] });
    };
    window.addEventListener('graph-cache-refresh', onRefresh);
    return () => window.removeEventListener('graph-cache-refresh', onRefresh);
  }, [client]);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
