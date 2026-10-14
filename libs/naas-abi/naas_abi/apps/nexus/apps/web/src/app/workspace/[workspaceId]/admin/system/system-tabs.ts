export type SystemTab =
  | 'overview'
  | 'services'
  | 'data'
  | 'jobs'
  | 'agents'
  | 'modules'
  | 'nats'
  | 'traffic'
  | 'traces';

export const SYSTEM_TABS: { id: SystemTab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'services', label: 'Services' },
  { id: 'data', label: 'Data' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'agents', label: 'Agents' },
  { id: 'modules', label: 'Modules' },
  { id: 'nats', label: 'NATS' },
  { id: 'traffic', label: 'Live traffic' },
  { id: 'traces', label: 'Traces' },
];

export function parseSystemTab(value: string | null | undefined): SystemTab {
  return SYSTEM_TABS.some((t) => t.id === value) ? (value as SystemTab) : 'overview';
}
