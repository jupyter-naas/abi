'use client';

import { Suspense, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { notFound } from 'next/navigation';
import { serviceForPage, type ServicePageSection } from '../../lib/service-pages';

function Loading() {
  return <p className="system-empty">Loading…</p>;
}

// The browser and its service views load on first open, as the heavier System views do.
const DataExplorer = dynamic(() => import('./explorer').then((m) => m.DataExplorer), { ssr: false, loading: Loading });

/** A kernel service's page: its data browser. */
export function ServicePage({ service }: { service: string }) {
  // The service's own view loads beside the browser, not after it (the registry is
  // imported here too, so it stays out of the page's first load).
  useEffect(() => {
    import('./services/registry').then((r) => r.loadServiceView(service)).catch(() => undefined);
  }, [service]);
  return (
    <Suspense fallback={<Loading />}>
      <DataExplorer key={service} service={service} />
    </Suspense>
  );
}

/** The page of `/settings/<section>/<slug>`, or a 404 when no service has that page. */
export function SectionServicePage({ section, slug }: { section: ServicePageSection; slug: string }) {
  const service = serviceForPage(section, slug);
  if (!service) notFound();
  return <ServicePage service={service} />;
}
