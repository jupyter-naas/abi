'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { ExternalLink } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { DOCKER_SERVICES, buildServiceUrl, resolveServiceHost } from '@/lib/docker-services';

export default function ServiceDetailPage() {
  const params = useParams();
  const serviceId = typeof params?.serviceId === 'string' ? params.serviceId : '';
  const service = useMemo(() => DOCKER_SERVICES.find((s) => s.id === serviceId), [serviceId]);

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
        Checking access...
      </div>
    );
  }

  if (authState === 'denied') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <h1 className="text-xl font-semibold">Forbidden</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          Platform superadmin role required. Set
          <code className="mx-1 rounded bg-muted px-1 py-0.5">is_superadmin: true</code>
          on the matching user in <code className="mx-1 rounded bg-muted px-1 py-0.5">config.local.yaml</code>
          and restart the API to grant access.
        </p>
      </div>
    );
  }

  if (!service) {
    return <p className="p-6 text-sm text-muted-foreground">Service not found.</p>;
  }

  const url = buildServiceUrl(service, resolveServiceHost());
  const embeddable = service.embeddable !== false;

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-shrink-0 items-baseline justify-between gap-4 border-b px-6 py-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">{service.label}</h1>
          <p className="truncate text-xs text-muted-foreground">
            {service.description}
            {embeddable ? `, embedded from ${url}` : ''}
          </p>
        </div>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-shrink-0 items-center gap-1.5 rounded border px-3 py-1 text-xs hover:bg-accent"
        >
          <ExternalLink size={14} />
          Open in new tab
        </a>
      </header>

      <div className="flex-1 overflow-hidden">
        {!embeddable ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <p className="max-w-md text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{service.label}</span> can&apos;t be
              embedded here, it refuses to load inside a frame (
              <code className="rounded bg-muted px-1 py-0.5">X-Frame-Options: DENY</code>). Open
              it in a new tab instead.
            </p>
          </div>
        ) : (
          <iframe
            key={service.id}
            src={url}
            title={service.label}
            className="h-full w-full border-0"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-downloads"
          />
        )}
      </div>
    </div>
  );
}
