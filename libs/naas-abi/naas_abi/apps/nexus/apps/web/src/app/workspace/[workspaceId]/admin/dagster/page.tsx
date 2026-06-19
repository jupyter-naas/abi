'use client';

import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { authFetch } from '@/stores/auth';

// Dagster web UI. Configurable so non-local environments can point at the
// orchestrator behind a reverse proxy; defaults to the docker-compose port.
const DAGSTER_URL = process.env.NEXT_PUBLIC_DAGSTER_URL || 'http://localhost:3001';

export default function AdminDagsterPage() {
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/me');
        if (!res.ok) {
          if (!cancelled) setAuthState('denied');
          return;
        }
        const data = await res.json();
        if (cancelled) return;
        setAuthState(data.is_superadmin ? 'authorized' : 'denied');
      } catch {
        if (!cancelled) setAuthState('denied');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (authState === 'checking') {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Checking access…
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <h1 className="text-xl font-semibold">Forbidden</h1>
        <p className="text-sm text-muted-foreground">
          Platform superadmin role required. Set
          <code className="mx-1 rounded bg-muted px-1 py-0.5">is_superadmin: true</code>
          on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.yaml</code>
          and restart the API to grant access.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold">Dagster</h1>
          <p className="text-xs text-muted-foreground">
            Data pipeline orchestration — embedded from {DAGSTER_URL}.
          </p>
        </div>
        <a
          href={DAGSTER_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 rounded border px-3 py-1 text-xs hover:bg-accent"
        >
          <ExternalLink size={14} />
          Open in new tab
        </a>
      </header>

      <div className="flex-1 overflow-hidden">
        <iframe
          src={DAGSTER_URL}
          title="Dagster"
          className="h-full w-full border-0"
          sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
        />
      </div>
    </div>
  );
}
