'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import { useSuperadminAccess } from '@/hooks/use-superadmin-access';
import { DOCKER_SERVICES, buildServiceUrl, resolveServiceHost } from '@/lib/docker-services';
import { buttonVariants } from '@/components/ui/button';
import { ServicesForbidden } from '../services-forbidden';

export default function ServiceDetailPage() {
  const params = useParams();
  const serviceId = typeof params?.serviceId === 'string' ? params.serviceId : '';
  const servicesPath = `/workspace/${params?.workspaceId}/settings/services`;
  const service = useMemo(() => DOCKER_SERVICES.find((s) => s.id === serviceId), [serviceId]);

  const authState = useSuperadminAccess();

  if (authState === 'checking') {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Checking access...
      </div>
    );
  }

  if (authState === 'denied') return <ServicesForbidden />;

  if (!service) {
    return (
      <div className="space-y-3 p-6">
        <Link href={servicesPath} className={buttonVariants({ variant: 'secondary' })}>
          <ArrowLeft size={16} /> All services
        </Link>
        <p className="text-sm text-muted-foreground">Service not found.</p>
      </div>
    );
  }

  const url = buildServiceUrl(service, resolveServiceHost());
  const embeddable = service.embeddable !== false;

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-shrink-0 items-center justify-between gap-4 border-b border-border px-6 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link href={servicesPath} className={buttonVariants({ variant: 'secondary' })}>
            <ArrowLeft size={16} /> All services
          </Link>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">{service.label}</h2>
            <p className="truncate text-xs text-muted-foreground">
              {service.description}
              {embeddable ? `, embedded from ${url}` : ''}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: 'secondary' })}
          >
            <ExternalLink size={14} />
            Open in new tab
          </a>
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        {!embeddable ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
            <p className="max-w-md text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{service.label}</span> can&apos;t be
              embedded here, it refuses to load inside a frame (
              <code className=" bg-muted px-1 py-0.5">X-Frame-Options: DENY</code>). Open
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
