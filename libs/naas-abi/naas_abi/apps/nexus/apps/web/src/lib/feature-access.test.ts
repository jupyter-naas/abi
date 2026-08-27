import { describe, expect, it } from 'vitest';

import {
  getFeatureForWorkspacePath,
  getFirstAllowedWorkspacePath,
  getWorkspaceSwitchPath,
  isWorkspacePathAllowed,
  mergeFeatureFlags,
  pathNeedsAgentCatalog,
  pathNeedsGraphExport,
} from './feature-access';

describe('mergeFeatureFlags', () => {
  it('keeps member defaults', () => {
    const flags = mergeFeatureFlags('member');

    expect(flags.maps).toBe(true);
    expect(flags.chat).toBe(true);
    expect(flags.files).toBe(true);
    expect(flags.slides).toBe(true);
    expect(flags.agents).toBe(false);
    expect(flags.apps).toBe(false);
    expect(flags.marketplace).toBe(false);
    expect(flags.search).toBe(false);
    expect(flags.ontology).toBe(false);
    expect(flags.graph).toBe(false);
    expect(flags.settings).toBe(false);
  });

  it('can enable apps and marketplace independently', () => {
    const flags = mergeFeatureFlags('member', { apps: true, marketplace: true });

    expect(flags.apps).toBe(true);
    expect(flags.marketplace).toBe(true);
    expect(flags.agents).toBe(false);
  });

  it('applies workspace overrides', () => {
    const flags = mergeFeatureFlags('member', { search: true, chat: false });

    expect(flags.chat).toBe(false);
    expect(flags.files).toBe(true);
    expect(flags.search).toBe(true);
  });
});

describe('getFeatureForWorkspacePath', () => {
  it('maps workspace paths to features', () => {
    expect(getFeatureForWorkspacePath('/workspace/ws1/maps')).toBe('maps');
    expect(getFeatureForWorkspacePath('/workspace/ws1/maps/presence')).toBe('maps');
    expect(getFeatureForWorkspacePath('/workspace/ws1/chat')).toBe('chat');
    expect(getFeatureForWorkspacePath('/workspace/ws1/search')).toBe('search');
    expect(getFeatureForWorkspacePath('/workspace/ws1/ontology')).toBe('ontology');
    expect(getFeatureForWorkspacePath('/workspace/ws1/graph')).toBe('graph');
    expect(getFeatureForWorkspacePath('/workspace/ws1/settings/agents')).toBe('agents');
    expect(getFeatureForWorkspacePath('/workspace/ws1/settings/theme')).toBe('settings.workspace');
    expect(getFeatureForWorkspacePath('/workspace/ws1/organization')).toBe('settings.organization');
    expect(getFeatureForWorkspacePath('/workspace/ws1/organization/billing')).toBe('settings.organization');
    expect(getFeatureForWorkspacePath('/workspace/ws1/apps')).toBe('apps');
    expect(getFeatureForWorkspacePath('/workspace/ws1/marketplace')).toBe('marketplace');
    expect(getFeatureForWorkspacePath('/workspace/ws1/help')).toBe('settings');
  });

  it('supports org-scoped rewritten routes', () => {
    expect(getFeatureForWorkspacePath('/org/acme/workspace/ws1/chat')).toBe('chat');
    expect(getFeatureForWorkspacePath('/org/acme/workspace/ws1/lab')).toBe('agents');
  });

  it('maps code and ide paths to the code feature', () => {
    expect(getFeatureForWorkspacePath('/workspace/ws1/code')).toBe('code');
    expect(getFeatureForWorkspacePath('/workspace/ws1/code/workspaces')).toBe('code');
    expect(getFeatureForWorkspacePath('/workspace/ws1/ide')).toBe('code');
  });

  it('maps slides paths to the slides feature', () => {
    expect(getFeatureForWorkspacePath('/workspace/ws1/slides')).toBe('slides');
    expect(getFeatureForWorkspacePath('/workspace/ws1/slides/new')).toBe('slides');
    expect(mergeFeatureFlags('owner').slides).toBe(true);
    expect(
      isWorkspacePathAllowed({ pathname: '/workspace/ws1/slides', role: 'member' }),
    ).toBe(true);
  });
});

describe('feature guards', () => {
  it('keeps code off by default and opt-in via flags', () => {
    expect(mergeFeatureFlags('owner').code).toBe(false);
    expect(mergeFeatureFlags('member').code).toBe(false);
    expect(mergeFeatureFlags('owner', { code: true }).code).toBe(true);
    expect(
      isWorkspacePathAllowed({ pathname: '/workspace/ws1/code', role: 'owner' }),
    ).toBe(false);
    expect(
      isWorkspacePathAllowed({
        pathname: '/workspace/ws1/code',
        role: 'owner',
        workspaceFlags: { code: true },
      }),
    ).toBe(true);
  });

  it('blocks disabled routes', () => {
    expect(
      isWorkspacePathAllowed({
        pathname: '/workspace/ws1/chat',
        role: 'member',
      }),
    ).toBe(true);
    expect(
      isWorkspacePathAllowed({
        pathname: '/workspace/ws1/graph',
        role: 'member',
      }),
    ).toBe(false);
  });
});

describe('getFirstAllowedWorkspacePath', () => {
  it('returns first enabled route', () => {
    expect(
      getFirstAllowedWorkspacePath({
        workspaceId: 'ws1',
        role: 'member',
      }),
    ).toBe('/workspace/ws1/chat');
  });
});

describe('getWorkspaceSwitchPath', () => {
  it('stays on the same section', () => {
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/apps',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/apps');
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/apps?open=fm-slides',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/apps');
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/chat/conv-42',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/chat');
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/maps/presence',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/maps/presence');
  });

  it('falls back when the target workspace lacks the section', () => {
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/apps',
        targetWorkspaceId: 'ws-member',
        role: 'member',
      }),
    ).toBe('/workspace/ws-member/chat');
  });

  it('preserves admin routes that are not feature-gated', () => {
    expect(
      getWorkspaceSwitchPath({
        pathname: '/workspace/ws-next-gen/admin/events',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/admin/events');
  });

  it('works with org-scoped rewritten paths', () => {
    expect(
      getWorkspaceSwitchPath({
        pathname: '/org/acme/workspace/ws-next-gen/apps',
        targetWorkspaceId: 'ws-other',
        role: 'owner',
      }),
    ).toBe('/workspace/ws-other/apps');
  });
});

describe('pathNeedsAgentCatalog', () => {
  it('is true on chat, lab, and agent settings', () => {
    expect(pathNeedsAgentCatalog('/workspace/ws1/chat')).toBe(true);
    expect(pathNeedsAgentCatalog('/workspace/ws1/chat/conv-1')).toBe(true);
    expect(pathNeedsAgentCatalog('/workspace/ws1/lab')).toBe(true);
    expect(pathNeedsAgentCatalog('/workspace/ws1/settings/agents')).toBe(true);
  });

  it('is false on apps and other sections', () => {
    expect(pathNeedsAgentCatalog('/workspace/ws1/apps')).toBe(false);
    expect(pathNeedsAgentCatalog('/workspace/ws1/files')).toBe(false);
    expect(pathNeedsAgentCatalog('/workspace/ws1/settings/theme')).toBe(false);
  });
});

describe('pathNeedsGraphExport', () => {
  it('is true only on graph routes', () => {
    expect(pathNeedsGraphExport('/workspace/ws1/graph/network')).toBe(true);
    expect(pathNeedsGraphExport('/workspace/ws1/apps')).toBe(false);
  });
});
