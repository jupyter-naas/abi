/**
 * Settings › Access › Services: the core services' access levels as the Users table shows them.
 * Pure: the view is `core-services.tsx`; the levels are `access-levels`' (`kind=service`).
 */
import { LEVEL_LABELS, type LevelRow } from '@/lib/access-model/access-levels';

export type ServiceColumnId = 'service' | 'access';
export const SERVICE_COLUMNS: { id: ServiceColumnId; label: string }[] = [
  { id: 'service', label: 'Service' },
  { id: 'access', label: 'Access' },
];

export function serviceCellValues(row: LevelRow, column: ServiceColumnId): string[] {
  return column === 'service' ? [row.label] : [LEVEL_LABELS[row.level]];
}

export function serviceSearchTexts(row: LevelRow): string[] {
  return [row.label, row.name, LEVEL_LABELS[row.level], ...Object.values(row.actions).flat()];
}

export const SERVICE_EXPORT_HEADERS = ['Service', 'Name', 'Access', 'Read', 'Write', 'Admin'];
export function serviceExportRow(row: LevelRow): string[] {
  return [
    row.label,
    row.name,
    LEVEL_LABELS[row.level],
    (row.actions.read ?? []).join('; '),
    (row.actions.write ?? []).join('; '),
    (row.actions.admin ?? []).join('; '),
  ];
}
