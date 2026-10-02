export type SystemTab = 'overview' | 'services' | 'modules' | 'nats' | 'traffic';

export const SYSTEM_TABS: { id: SystemTab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'services', label: 'Services' },
  { id: 'modules', label: 'Modules' },
  { id: 'nats', label: 'NATS' },
  { id: 'traffic', label: 'Live traffic' },
];

export function parseSystemTab(value: string | null | undefined): SystemTab {
  return SYSTEM_TABS.some((t) => t.id === value) ? (value as SystemTab) : 'overview';
}
