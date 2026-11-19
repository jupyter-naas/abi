/**
 * The data browsers of the kernel services, one Platform Settings page each, in the
 * group of the question it answers: is it running (System), what happened (Activity),
 * what is connected (Resources), what is stored (Data). No React here:
 * src/middleware.ts imports it through the redirects.
 */
import { safeDecode } from './page-helpers';

export type ServicePageSection = 'system' | 'activity' | 'resources' | 'data';

export interface ServicePage {
  /** The service's name in the data API. */
  service: string;
  section: ServicePageSection;
  /** The last segment of the page's path. */
  slug: string;
  /** Its sidebar label: the service view's label. */
  label: string;
}

export const SECTION_PATHS: Record<ServicePageSection, string> = {
  system: '/settings/system',
  activity: '/settings/activity',
  resources: '/settings/resources',
  data: '/settings/data',
};

export const SERVICE_PAGES: readonly ServicePage[] = [
  { service: 'discovery', section: 'system', slug: 'discovery', label: 'Discovery' },
  { service: 'bus', section: 'system', slug: 'bus', label: 'Bus' },
  { service: 'event', section: 'activity', slug: 'event-store', label: 'Event store' },
  { service: 'activity_log', section: 'activity', slug: 'log', label: 'Activity log' },
  { service: 'model_registry', section: 'resources', slug: 'models', label: 'Models' },
  { service: 'secret', section: 'resources', slug: 'secrets', label: 'Secrets' },
  { service: 'email', section: 'resources', slug: 'email', label: 'Email' },
  { service: 'source_control', section: 'resources', slug: 'source-control', label: 'Source control' },
  {
    service: 'coding_environment',
    section: 'resources',
    slug: 'coding-environments',
    label: 'Coding environments',
  },
  { service: 'triple_store', section: 'data', slug: 'knowledge-graph', label: 'Knowledge graph' },
  { service: 'vector_store', section: 'data', slug: 'vector-store', label: 'Vector store' },
  { service: 'document', section: 'data', slug: 'documents', label: 'Documents' },
  { service: 'dataset', section: 'data', slug: 'datasets', label: 'Datasets' },
  { service: 'object_storage', section: 'data', slug: 'object-storage', label: 'Object storage' },
  { service: 'keyvalue', section: 'data', slug: 'key-value', label: 'Key-value' },
  { service: 'cache', section: 'data', slug: 'cache', label: 'Cache' },
];

export function servicePagesIn(section: ServicePageSection): ServicePage[] {
  return SERVICE_PAGES.filter((page) => page.section === section);
}

/**
 * A service's page. A service without a page of its own (one this list does not
 * know yet) opens under Data by its API name, so its data stays reachable.
 */
export function servicePagePath(service: string): string {
  const page = SERVICE_PAGES.find((p) => p.service === service);
  return page
    ? `${SECTION_PATHS[page.section]}/${page.slug}`
    : `${SECTION_PATHS.data}/${encodeURIComponent(service)}`;
}

/**
 * The service a section's page browses, or null when there is none. Under Data, a
 * slug that is not a page's is taken as a service's API name (see servicePagePath).
 */
export function serviceForPage(section: ServicePageSection, slug: string): string | null {
  const name = safeDecode(slug);
  const page = SERVICE_PAGES.find((p) => p.section === section && p.slug === name);
  if (page) return page.service;
  const known = SERVICE_PAGES.some((p) => p.slug === name || p.service === name);
  return section === 'data' && name && !known ? name : null;
}
