/**
 * The pages of the System app: the System group of the Platform Settings sidebar at
 * `/settings/system[/<view>]`, and the Activity group at `/settings/activity/<view>`.
 * No React here: src/middleware.ts imports it.
 */
import { PLATFORM_ACCESS_PATH } from '@/components/access/access-paths';
import { SECTION_PATHS, servicePagePath } from '../lib/service-pages';

export type SystemView =
  | 'overview'
  | 'services'
  | 'jobs'
  | 'agents'
  | 'modules'
  | 'nats'
  | 'traffic'
  | 'traces'
  | 'events';

export const SYSTEM_PATH = SECTION_PATHS.system;
export const ACTIVITY_PATH = SECTION_PATHS.activity;

/** The map of the ABI code, one page per view (Settings › Platform › System). */
export const INFRASTRUCTURE_LAYERS_PATH = `${SYSTEM_PATH}/layers`;
export const INFRASTRUCTURE_DIAGRAMS_PATH = `${SYSTEM_PATH}/diagrams`;

export const SYSTEM_VIEWS: { id: SystemView; label: string; description: string }[] = [
  { id: 'overview', label: 'Overview', description: 'Health of the kernel services, modules and the NATS network' },
  { id: 'services', label: 'Services', description: 'Kernel services and their adapters' },
  { id: 'modules', label: 'Modules', description: 'Engine and remote modules, their leases and readiness' },
  { id: 'agents', label: 'Agents', description: 'Agents of the engine and of remote modules' },
  { id: 'jobs', label: 'Jobs', description: 'Module jobs and workflows, their runs and schedules' },
  { id: 'nats', label: 'NATS', description: 'The broker, its connections and JetStream' },
  { id: 'traffic', label: 'Live traffic', description: 'Calls between services as they happen' },
  { id: 'traces', label: 'Traces', description: 'Search traces and read their spans' },
  { id: 'events', label: 'Events', description: 'Recent platform activity, as BFO processes' },
];

/** The views of the Activity group: what happened, rather than what runs. */
export const ACTIVITY_VIEWS: readonly SystemView[] = ['traffic', 'traces', 'events'];

export function isSystemView(value: string | null | undefined): value is SystemView {
  return SYSTEM_VIEWS.some((view) => view.id === value);
}

/** `/settings/system` for the overview, `/settings/{system,activity}/<view>` for the others. */
export function systemViewPath(view: SystemView): string {
  if (view === 'overview') return SYSTEM_PATH;
  return `${ACTIVITY_VIEWS.includes(view) ? ACTIVITY_PATH : SYSTEM_PATH}/${view}`;
}

/** A trace in the Traces page. */
export function systemTracePath(traceId: string): string {
  return `${systemViewPath('traces')}?trace=${encodeURIComponent(traceId)}`;
}

/**
 * Where a link to the old Data tab (`?service=<name>&in=...&item=...`) goes now: that
 * service's page, the place in it kept; without a service, the first Data page.
 */
export function legacyDataPath(params: URLSearchParams): string {
  const rest = new URLSearchParams(params);
  const service = rest.get('service');
  rest.delete('service');
  const path = service ? servicePagePath(service) : servicePagePath('triple_store');
  const query = rest.toString();
  return query ? `${path}?${query}` : path;
}

/**
 * Where an old System link (`/workspace/<id>/admin/system?tab=<tab>`) goes now: the
 * tab's page, its other query parameters kept. Access is Platform › Access, Data the
 * service's page; a missing or unknown tab is the overview.
 */
export function legacySystemTabPath(params: URLSearchParams): string {
  const rest = new URLSearchParams(params);
  const tab = rest.get('tab');
  rest.delete('tab');
  if (tab === 'data') return legacyDataPath(rest);
  const path =
    tab === 'access' ? PLATFORM_ACCESS_PATH : systemViewPath(isSystemView(tab) && tab !== 'events' ? tab : 'overview');
  const query = rest.toString();
  return query ? `${path}?${query}` : path;
}
