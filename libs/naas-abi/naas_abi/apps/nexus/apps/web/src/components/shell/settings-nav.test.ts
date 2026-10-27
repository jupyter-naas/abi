import { describe, expect, it } from 'vitest';
import {
  SETTINGS_GROUPS,
  settingsItemFor,
  visibleSettingsGroups,
} from '@/components/shell/settings-nav';
import { describeModuleResources, type WorkspaceResources } from '@/lib/workspace-resources';

function resources(over: Partial<WorkspaceResources> = {}): WorkspaceResources {
  return {
    organization_id: 'org-1',
    can_edit_set: false,
    features: ['agents', 'apps', 'files', 'graph', 'maps', 'ontology', 'search', 'skills', 'settings'],
    modules: [],
    totals: { agents: 2, apps: 1, workflows: 0, pipelines: 1 },
    ...over,
  };
}

const labels = (groups: ReturnType<typeof visibleSettingsGroups>) =>
  groups.flatMap((group) => group.items.map((item) => item.label));

describe('workspace settings nav', () => {
  it('lists every entry the set has', () => {
    expect(labels(visibleSettingsGroups(resources()))).toEqual(
      SETTINGS_GROUPS.flatMap((group) => group.items.map((item) => item.label))
    );
  });

  it('hides an entry whose feature is outside the set', () => {
    const shown = labels(visibleSettingsGroups(resources({ features: ['apps', 'settings'] })));
    expect(shown).toContain('Apps');
    expect(shown).not.toContain('Agents');
    expect(shown).not.toContain('Maps');
    // No feature: always there.
    expect(shown).toContain('Models');
    expect(shown).toContain('General');
  });

  it('hides Apps and Workflows when the set has none of theirs', () => {
    const none = { agents: 0, apps: 0, workflows: 0, pipelines: 0 };
    const shown = labels(visibleSettingsGroups(resources({ totals: none })));
    expect(shown).not.toContain('Apps');
    expect(shown).not.toContain('Workflows');
    // Agents the workspace builds itself stay manageable.
    expect(shown).toContain('Agents');
    const pipelines = labels(visibleSettingsGroups(resources({ totals: { ...none, pipelines: 2 } })));
    expect(pipelines).toContain('Workflows');
  });

  it('follows the caller flags while the set is unknown', () => {
    const shown = labels(visibleSettingsGroups(null, { apps: false, maps: true }));
    expect(shown).not.toContain('Apps');
    expect(shown).toContain('Maps');
    expect(shown).toContain('Workflows');
  });

  it('finds the entry of a path, nested pages included', () => {
    expect(settingsItemFor('/workspace/ws-1/settings/apps')?.label).toBe('Apps');
    expect(settingsItemFor('/workspace/ws-1/settings/agents/a-1')?.label).toBe('Agents');
    expect(settingsItemFor('/workspace/ws-1/settings/infrastructure')).toBeUndefined();
    expect(settingsItemFor('/workspace/ws-1/chat')).toBeUndefined();
  });

  it('describes a module by what it has in the set', () => {
    expect(
      describeModuleResources({ module: 'p', agents: 2, apps: 1, workflows: 0, pipelines: 1 })
    ).toBe('2 agents · 1 app · 1 pipeline');
  });
});
