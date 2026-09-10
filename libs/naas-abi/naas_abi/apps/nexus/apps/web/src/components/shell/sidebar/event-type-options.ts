import type { EventTypeOption } from '@/stores/events';

export interface EventTypePickerOption {
  /** Class URI; '' is "All event types". */
  value: string;
  label: string;
}

const ALL_LABEL = 'All event types';

/** Rows for the event-type picker: All first, then types matching `query` by label or URI. */
export function eventTypeOptions(
  types: readonly EventTypeOption[],
  query: string,
): EventTypePickerOption[] {
  const q = query.trim().toLowerCase();
  const matched = types
    .filter((type) => !q || type.label.toLowerCase().includes(q) || type.uri.toLowerCase().includes(q))
    .map((type) => ({ value: type.uri, label: type.label }));
  return q ? matched : [{ value: '', label: ALL_LABEL }, ...matched];
}

export function eventTypeTriggerLabel(types: readonly EventTypeOption[], value: string): string {
  if (!value) return `${ALL_LABEL} (${types.length})`;
  return types.find((type) => type.uri === value)?.label ?? value;
}
