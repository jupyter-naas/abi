import { describe, expect, it } from 'vitest';

import { eventTypeOptions, eventTypeTriggerLabel } from './event-type-options';

const types = [
  { uri: 'https://ex.org/abi#ObjectPut', label: 'PUT Object' },
  { uri: 'https://ex.org/abi#AnalyticEvent', label: 'Recorded - Analytic Event' },
  { uri: 'https://ex.org/abi#AgentRun', label: 'Agent run' },
];

describe('eventTypeOptions', () => {
  it('leads with All, then every type, when there is no query', () => {
    const options = eventTypeOptions(types, '');
    expect(options.map((o) => o.value)).toEqual(['', ...types.map((t) => t.uri)]);
    expect(options[0].label).toBe('All event types');
  });

  it('matches labels case-insensitively and drops All while searching', () => {
    expect(eventTypeOptions(types, 'analytic').map((o) => o.label)).toEqual([
      'Recorded - Analytic Event',
    ]);
  });

  it('matches the class URI too, so a local name finds its label', () => {
    expect(eventTypeOptions(types, 'objectput').map((o) => o.label)).toEqual(['PUT Object']);
  });

  it('ignores surrounding whitespace in the query', () => {
    expect(eventTypeOptions(types, '  agent ').map((o) => o.label)).toEqual(['Agent run']);
  });

  it('returns nothing when no type matches', () => {
    expect(eventTypeOptions(types, 'zzz')).toEqual([]);
  });
});

describe('eventTypeTriggerLabel', () => {
  it('shows All with the type count when unfiltered', () => {
    expect(eventTypeTriggerLabel(types, '')).toBe('All event types (3)');
  });

  it('shows the selected type label', () => {
    expect(eventTypeTriggerLabel(types, types[1].uri)).toBe('Recorded - Analytic Event');
  });

  it('falls back to the URI while the type list has not loaded', () => {
    expect(eventTypeTriggerLabel([], types[0].uri)).toBe(types[0].uri);
  });
});
