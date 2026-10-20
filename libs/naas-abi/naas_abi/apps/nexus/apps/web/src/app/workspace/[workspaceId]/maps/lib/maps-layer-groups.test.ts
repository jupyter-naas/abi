import { describe, expect, it } from 'vitest';

import {
  DEFAULT_LAYER_GROUP,
  layerGroupKey,
  layerGroupLabels,
  layoutGroup,
  legacyGroupLabel,
  takeLegacyLocalGroups,
} from './maps-layer-groups';

describe('legacyGroupLabel', () => {
  it('maps pre-group category slugs to labels', () => {
    expect(legacyGroupLabel('public')).toBe('Public');
    expect(legacyGroupLabel('environment')).toBe('Environment');
    expect(legacyGroupLabel('organizations-facility')).toBe('Organizations Facilities');
    expect(legacyGroupLabel('custom')).toBe(DEFAULT_LAYER_GROUP);
    expect(legacyGroupLabel('Field Offices')).toBe('Field Offices');
    expect(legacyGroupLabel('')).toBe(DEFAULT_LAYER_GROUP);
    expect(legacyGroupLabel(undefined)).toBe(DEFAULT_LAYER_GROUP);
  });
});

describe('layoutGroup', () => {
  it('prefers group, then the legacy category', () => {
    expect(layoutGroup({ group: ' Partners ', category: 'public' })).toBe('Partners');
    expect(layoutGroup({ category: 'sigint' })).toBe('SIGINT');
    expect(layoutGroup({})).toBe(DEFAULT_LAYER_GROUP);
  });
});

describe('layerGroupLabels', () => {
  it('derives groups from feeds: case-insensitive, sorted, Custom last', () => {
    expect(
      layerGroupLabels(['Situation', 'Custom', 'environment', 'Environment', ' ', 'SIGINT']),
    ).toEqual(['environment', 'SIGINT', 'Situation', 'Custom']);
    expect(layerGroupKey(' Environment ')).toBe(layerGroupKey('environment'));
  });
});

function memoryStorage(): Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
  const items = new Map<string, string>();
  return {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => void items.set(key, value),
    removeItem: (key) => void items.delete(key),
  };
}

describe('takeLegacyLocalGroups', () => {
  it('returns browser-only group choices as labels and clears them', () => {
    const storage = memoryStorage();
    storage.setItem(
      'nexus-maps-custom-layer-groups',
      JSON.stringify({ 'ws-1': [{ id: 'user-ops', label: 'Operations' }] }),
    );
    storage.setItem(
      'nexus-maps-workspace-layer-meta',
      JSON.stringify({
        'ws-1': { offices: { groupId: 'user-ops' }, plants: { groupId: 'environment' } },
        'ws-2': { other: { groupId: 'user-x' } },
      }),
    );
    expect(takeLegacyLocalGroups('ws-1', storage)).toEqual({
      layers: { offices: 'Operations', plants: 'Environment' },
      labels: { 'user-ops': 'Operations' },
    });
    expect(takeLegacyLocalGroups('ws-1', storage)).toEqual({ layers: {}, labels: {} });
    // Other workspaces keep theirs until they are opened.
    expect(takeLegacyLocalGroups('ws-2', storage).layers).toEqual({ other: 'user-x' });
  });
});
