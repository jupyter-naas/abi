'use client';

import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';
import { DOCKER_SERVICES } from '@/lib/docker-services';

export default function AdminServicesPage() {
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'denied'>('checking');
  const [activeId, setActiveId] = useState<string>(DOCKER_SERVICES[0]?.id ?? '');

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
          on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.local.yaml</code>
          and restart the API to grant access.
        </p>
      </div>
    );
  }

  const active = DOCKER_SERVICES.find((s) => s.id === activeId) ?? DOCKER_SERVICES[0];

  return (
    <div className="flex h-full flex-col bg-background text-foreground">
      <header className="flex flex-col gap-3 border-b px-6 py-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold">Services</h1>
            <p className="text-xs text-muted-foreground">
              {active ? `${active.description} — embedded from ${active.url}` : 'No services configured.'}
            </p>
          </div>
          {active && (
            <a
              href={active.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded border px-3 py-1 text-xs hover:bg-accent"
            >
              <ExternalLink size={14} />
              Open in new tab
            </a>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {DOCKER_SERVICES.map((service) => (
            <button
              key={service.id}
              onClick={() => setActiveId(service.id)}
              title={service.url}
              className={cn(
                'rounded border px-3 py-1 text-xs transition-colors',
                service.id === activeId
                  ? 'border-workspace-accent bg-workspace-accent-15 text-workspace-accent'
                  : 'text-muted-foreground hover:bg-accent'
              )}
            >
              {service.label}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        {!active ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No services found.
          </div>
        ) : active.embeddable === false ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <p className="max-w-md text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{active.label}</span> can&apos;t be embedded
              here — it refuses to load inside a frame (<code className="rounded bg-muted px-1 py-0.5">X-Frame-Options: DENY</code>).
              Open it in a new tab instead.
            </p>
            <a
              href={active.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm hover:bg-accent"
            >
              <ExternalLink size={14} />
              Open {active.label}
            </a>
          </div>
        ) : (
          <iframe
            // Force a fresh element per service so the browser fully reloads
            // the embedded app instead of reusing the previous history entry.
            key={active.id}
            src={active.url}
            title={active.label}
            className="h-full w-full border-0"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
          />
        )}
      </div>
    </div>
  );
}
