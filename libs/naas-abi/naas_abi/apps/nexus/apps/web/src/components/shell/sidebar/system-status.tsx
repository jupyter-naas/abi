'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface ServiceStatus {
  name: string;
  label: string;
  url: string;
  healthUrl: string;
  port: number;
}

const SERVICES: ServiceStatus[] = [
  {
    name: 'api',
    label: 'API',
    url: 'http://localhost:9879',
    healthUrl: 'http://localhost:9879/health',
    port: 9879,
  },
  {
    name: 'svc',
    label: 'SVC',
    url: 'http://localhost:8080',
    healthUrl: 'http://localhost:8080',
    port: 8080,
  },
];

type Status = 'checking' | 'online' | 'offline';

function usePing(healthUrl: string, intervalMs = 15000): Status {
  const [status, setStatus] = useState<Status>('checking');

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch(healthUrl, {
          method: 'GET',
          signal: AbortSignal.timeout(3000),
          cache: 'no-store',
        });
        if (!cancelled) setStatus(res.ok ? 'online' : 'offline');
      } catch {
        if (!cancelled) setStatus('offline');
      }
    };

    check();
    const timer = setInterval(check, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [healthUrl, intervalMs]);

  return status;
}

function StatusDot({ status }: { status: Status }) {
  return (
    <span className="relative flex h-1.5 w-1.5 flex-shrink-0">
      {status === 'online' && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
      )}
      <span
        className={cn(
          'relative inline-flex h-1.5 w-1.5 rounded-full',
          status === 'online' && 'bg-emerald-400',
          status === 'offline' && 'bg-red-500',
          status === 'checking' && 'bg-muted-foreground/40'
        )}
      />
    </span>
  );
}

function ServiceLink({ service, collapsed }: { service: ServiceStatus; collapsed: boolean }) {
  const status = usePing(service.healthUrl);

  return (
    <a
      href={service.url}
      target="_blank"
      rel="noopener noreferrer"
      title={`${service.label} · localhost:${service.port} · ${status}`}
      className={cn(
        'group flex items-center gap-1.5 rounded px-1.5 py-1 transition-colors',
        'hover:bg-muted/40',
        collapsed ? 'justify-center' : 'flex-1'
      )}
    >
      <StatusDot status={status} />
      {!collapsed && (
        <span className="font-mono text-[10px] tracking-widest text-muted-foreground/60 group-hover:text-muted-foreground transition-colors">
          {service.label}
          <span className="text-muted-foreground/30 ml-0.5">:{service.port}</span>
        </span>
      )}
    </a>
  );
}

export function SystemStatus({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      className={cn(
        'border-t border-border/30 bg-background/30 backdrop-blur-sm',
        collapsed ? 'flex flex-col items-center gap-1 py-2 px-2' : 'flex items-center gap-0.5 px-2 py-1.5'
      )}
    >
      {!collapsed && (
        <span className="font-mono text-[9px] tracking-[0.15em] text-muted-foreground/30 uppercase mr-1 flex-shrink-0">
          sys
        </span>
      )}
      {SERVICES.map((svc) => (
        <ServiceLink key={svc.name} service={svc} collapsed={collapsed} />
      ))}
    </div>
  );
}
