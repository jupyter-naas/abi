/**
 * The System pages, each one an item of the Platform Settings sidebar at
 * `/settings/system[/<view>]`. No React here: src/middleware.ts imports it.
 */
export type SystemView =
  | 'overview'
  | 'services'
  | 'data'
  | 'jobs'
  | 'agents'
  | 'modules'
  | 'nats'
  | 'traffic'
  | 'traces'
  | 'events';

export const SYSTEM_PATH = '/settings/system';

/** Roles & permissions, which was System's Access tab. */
export const ROLES_PATH = '/settings/roles';

export const SYSTEM_VIEWS: { id: SystemView; label: string; description: string }[] = [
  { id: 'overview', label: 'Overview', description: 'Health of the kernel services, modules and the NATS network' },
  { id: 'services', label: 'Services', description: 'Kernel services and their adapters' },
  { id: 'data', label: 'Data', description: 'What each kernel service holds' },
  { id: 'jobs', label: 'Jobs', description: 'Module jobs and workflows, their runs and schedules' },
  { id: 'agents', label: 'Agents', description: 'Agents of the engine and of remote modules' },
  { id: 'modules', label: 'Modules', description: 'Engine and remote modules, their leases and readiness' },
  { id: 'nats', label: 'NATS', description: 'The broker, its connections and JetStream' },
  { id: 'traffic', label: 'Live traffic', description: 'Calls between services as they happen' },
  { id: 'traces', label: 'Traces', description: 'Search traces and read their spans' },
  { id: 'events', label: 'Events', description: 'Recent platform activity, as BFO processes' },
];

export function isSystemView(value: string | null | undefined): value is SystemView {
  return SYSTEM_VIEWS.some((view) => view.id === value);
}

/** `/settings/system` for the overview, `/settings/system/<view>` for the others. */
export function systemViewPath(view: SystemView): string {
  return view === 'overview' ? SYSTEM_PATH : `${SYSTEM_PATH}/${view}`;
}

/** A trace in the Traces page. */
export function systemTracePath(traceId: string): string {
  return `${systemViewPath('traces')}?trace=${encodeURIComponent(traceId)}`;
}

/**
 * Where an old System link (`/workspace/<id>/admin/system?tab=<tab>`) goes now: the
 * tab's page, its other query parameters kept. Access is Roles & permissions; a
 * missing or unknown tab is the overview.
 */
export function legacySystemTabPath(params: URLSearchParams): string {
  const rest = new URLSearchParams(params);
  const tab = rest.get('tab');
  rest.delete('tab');
  const path =
    tab === 'access' ? ROLES_PATH : systemViewPath(isSystemView(tab) && tab !== 'events' ? tab : 'overview');
  const query = rest.toString();
  return query ? `${path}?${query}` : path;
}
