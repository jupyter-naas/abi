import { describe, expect, it } from 'vitest';

import {
  FEATURE_OFFICE_AGENTS,
  featureChatContext,
  featureOpenResource,
  getPaneSurfaceForPath,
  isFeatureOfficeAgent,
  resourceFromPath,
} from './feature-office-agents';
import {
  pickFeatureOfficeAgent,
  pickFeaturePaneAgent,
  pickSlidesOfficeAgent,
} from './pick-workspace-default-agent';

const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
const slides = {
  id: 'slides',
  enabled: true,
  isDefault: false,
  name: 'Slides',
  class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
};
const apps = {
  id: 'apps',
  enabled: true,
  isDefault: false,
  name: 'Apps',
  class_name: 'naas_abi.agents.AppsAgent/AppsAgent',
};

const abi = {
  id: 'abi',
  enabled: true,
  isDefault: false,
  name: 'Abi',
  class_name: 'naas_abi.agents.AbiAgent/AbiAgent',
};

describe('FEATURE_OFFICE_AGENTS', () => {
  it('maps every feature to its office agent, never Home or Chat', () => {
    expect(FEATURE_OFFICE_AGENTS.slides?.className).toBe('SlidesAgent');
    expect(FEATURE_OFFICE_AGENTS.apps?.className).toBe('AppsAgent');
    expect(FEATURE_OFFICE_AGENTS.graph?.className).toBe('KnowledgeGraphAgent');
    expect(FEATURE_OFFICE_AGENTS['settings.organization']?.className).toBe('SettingsAgent');
    expect(FEATURE_OFFICE_AGENTS.skills?.className).toBe('AgentCatalogAgent');
    expect(FEATURE_OFFICE_AGENTS.chat).toBeUndefined();
    expect(Object.values(FEATURE_OFFICE_AGENTS).map((a) => a?.className)).not.toContain(
      'AbiAgent',
    );
  });
});

describe('getPaneSurfaceForPath', () => {
  it('names the feature, or nothing on Home and other routes', () => {
    expect(getPaneSurfaceForPath('/workspace/ws-1/apps')).toBe('apps');
    expect(getPaneSurfaceForPath('/workspace/ws-1/graph/network')).toBe('graph');
    expect(getPaneSurfaceForPath('/workspace/ws-1/help')).toBe('settings');
    expect(getPaneSurfaceForPath('/workspace/ws-1/home')).toBeNull();
    expect(getPaneSurfaceForPath('/workspace/ws-1/admin/events')).toBeNull();
    expect(getPaneSurfaceForPath(null)).toBeNull();
  });
});

describe('resourceFromPath', () => {
  it('reads open items that live in the route', () => {
    expect(resourceFromPath('/workspace/ws-1/datasets/sales/orders')).toEqual({
      feature: 'datasets',
      kind: 'dataset',
      id: 'sales/orders',
    });
    expect(resourceFromPath('/workspace/ws-1/maps/earthquakes')?.id).toBe('earthquakes');
    expect(resourceFromPath('/workspace/ws-1/settings/agents/agent-7')).toEqual({
      feature: 'agents',
      kind: 'agent',
      id: 'agent-7',
    });
    expect(resourceFromPath('/workspace/ws-1/settings/skills/sk-1')?.kind).toBe('skill');
    expect(resourceFromPath('/workspace/ws-1/code/r/abi/monorepo/pulls')).toEqual({
      feature: 'code',
      kind: 'repo',
      id: 'abi/monorepo',
    });
  });

  it('is null on list routes', () => {
    expect(resourceFromPath('/workspace/ws-1/datasets')).toBeNull();
    expect(resourceFromPath('/workspace/ws-1/settings/agents')).toBeNull();
    expect(resourceFromPath('/workspace/ws-1/code/repos')).toBeNull();
  });
});

describe('featureOpenResource', () => {
  it('prefers what the page published for this feature', () => {
    const app = { feature: 'apps' as const, kind: 'app', id: 'm:wsr' };
    expect(featureOpenResource('/workspace/ws-1/apps', app)).toEqual(app);
    expect(featureOpenResource('/workspace/ws-1/maps/iss', app)?.id).toBe('iss');
  });
});

describe('isFeatureOfficeAgent', () => {
  it('matches by name or by naas_abi class', () => {
    expect(isFeatureOfficeAgent({ name: 'Apps' }, 'apps')).toBe(true);
    expect(
      isFeatureOfficeAgent({ name: 'Renamed', class_name: 'naas_abi.agents.AppsAgent/AppsAgent' }, 'apps'),
    ).toBe(true);
  });

  it('ignores lookalikes from other modules and features without an agent', () => {
    expect(
      isFeatureOfficeAgent({ name: 'Shop', class_name: 'acme.agents.ShopAppsAgent/ShopAppsAgent' }, 'apps'),
    ).toBe(false);
    expect(isFeatureOfficeAgent({ name: 'Apps' }, 'chat')).toBe(false);
  });
});

describe('pickFeaturePaneAgent', () => {
  it('binds Apps on the Apps section when the workspace lists it', () => {
    expect(pickFeaturePaneAgent([orchestrator, slides, apps], 'apps')?.id).toBe('apps');
  });

  it('falls back to the workspace default when Apps is not on the roster', () => {
    expect(pickFeaturePaneAgent([orchestrator, slides], 'apps')?.id).toBe('default');
  });

  it('keeps the workspace default on Home, Chat, and routes without a feature', () => {
    expect(pickFeaturePaneAgent([orchestrator, apps], 'chat')?.id).toBe('default');
    expect(pickFeaturePaneAgent([orchestrator, apps], null)?.id).toBe('default');
  });

  it('falls back to Abi when the workspace has no default', () => {
    const noDefault = { ...orchestrator, isDefault: false };
    expect(pickFeaturePaneAgent([noDefault, apps, abi], null)?.id).toBe('abi');
    expect(pickFeaturePaneAgent([noDefault, apps, abi], 'chat')?.id).toBe('abi');
    expect(pickFeaturePaneAgent([noDefault, abi], 'apps')?.id).toBe('abi');
  });

  it('skips a disabled office agent', () => {
    expect(pickFeaturePaneAgent([orchestrator, { ...apps, enabled: false }], 'apps')?.id).toBe(
      'default',
    );
  });

  it('does not let Apps answer on Slides', () => {
    expect(pickSlidesOfficeAgent([orchestrator, apps, slides])?.id).toBe('slides');
    expect(pickFeatureOfficeAgent([orchestrator, apps], 'slides')).toBeUndefined();
  });
});

describe('featureChatContext', () => {
  const path = '/workspace/ws-1/apps';

  it('names the section and the open app', () => {
    expect(
      featureChatContext(path, { feature: 'apps', kind: 'app', id: 'acme.module:wsr', label: 'WSR' }),
    ).toEqual({
      feature: {
        key: 'apps',
        path,
        resource: { kind: 'app', id: 'acme.module:wsr', label: 'WSR' },
      },
    });
  });

  it('sends the open app project and its recent preview errors', () => {
    const editor = '/workspace/ws-1/apps/p/budget-tracker';
    expect(getPaneSurfaceForPath(editor)).toBe('apps');
    const errors = ['e1', 'e2', 'e3', 'e4', 'e5', 'e6'];
    expect(
      featureChatContext(editor, {
        feature: 'apps',
        kind: 'app_project',
        id: 'budget-tracker',
        label: 'Budget Tracker',
        errors,
      }),
    ).toEqual({
      feature: {
        key: 'apps',
        path: editor,
        resource: { kind: 'app_project', id: 'budget-tracker', label: 'Budget Tracker' },
        errors: errors.slice(-5),
      },
    });
  });

  it('sends the section alone when nothing is open', () => {
    expect(featureChatContext(path, null)).toEqual({ feature: { key: 'apps', path } });
  });

  it('drops a resource published by another feature', () => {
    expect(
      featureChatContext('/workspace/ws-1/ontology', { feature: 'apps', kind: 'app', id: 'x' }),
    ).toEqual({ feature: { key: 'ontology', path: '/workspace/ws-1/ontology' } });
  });

  it('carries route-derived items', () => {
    expect(featureChatContext('/workspace/ws-1/datasets/sales/orders', null)?.feature.resource).toEqual({
      kind: 'dataset',
      id: 'sales/orders',
    });
  });

  it('is null on Chat, on Slides, and off feature routes', () => {
    expect(featureChatContext('/workspace/ws-1/chat', null)).toBeNull();
    expect(featureChatContext('/workspace/ws-1/slides/deck-1', null)).toBeNull();
    expect(featureChatContext('/workspace/ws-1/home', null)).toBeNull();
    expect(featureChatContext(null, null)).toBeNull();
  });
});
