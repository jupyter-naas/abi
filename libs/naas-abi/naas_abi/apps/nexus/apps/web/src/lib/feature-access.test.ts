import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getFeatureForWorkspacePath,
  getFirstAllowedWorkspacePath,
  isWorkspacePathAllowed,
  mergeFeatureFlags,
} from './feature-access';

test('mergeFeatureFlags keeps member defaults', () => {
  const flags = mergeFeatureFlags('member');

  assert.equal(flags.chat, true);
  assert.equal(flags.files, true);
  assert.equal(flags.agents, false);
  assert.equal(flags.apps, false);
  assert.equal(flags.marketplace, false);
  assert.equal(flags.search, false);
  assert.equal(flags.ontology, false);
  assert.equal(flags.graph, false);
  assert.equal(flags.settings, false);
});

test('mergeFeatureFlags can enable apps and marketplace independently', () => {
  const flags = mergeFeatureFlags('member', { apps: true, marketplace: true });

  assert.equal(flags.apps, true);
  assert.equal(flags.marketplace, true);
  assert.equal(flags.agents, false);
});

test('mergeFeatureFlags applies workspace overrides', () => {
  const flags = mergeFeatureFlags('member', { search: true, chat: false });

  assert.equal(flags.chat, false);
  assert.equal(flags.files, true);
  assert.equal(flags.search, true);
});

test('guard maps workspace paths to features', () => {
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/chat'), 'chat');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/search'), 'search');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/ontology'), 'ontology');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/graph'), 'graph');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/settings/agents'), 'agents');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/settings/theme'), 'settings.workspace');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/organization'), 'settings.organization');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/organization/billing'), 'settings.organization');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/apps'), 'apps');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/marketplace'), 'marketplace');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/help'), 'settings');
});

test('guard supports org-scoped rewritten routes', () => {
  assert.equal(getFeatureForWorkspacePath('/org/acme/workspace/ws1/chat'), 'chat');
  assert.equal(getFeatureForWorkspacePath('/org/acme/workspace/ws1/lab'), 'agents');
});

test('guard maps code and ide paths to the code feature', () => {
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/code'), 'code');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/code/workspaces'), 'code');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/ide'), 'code');
});

test('code feature is off by default and opt-in via flags', () => {
  // Opt-in: even an owner does not get code from the default baseline.
  assert.equal(mergeFeatureFlags('owner').code, false);
  assert.equal(mergeFeatureFlags('member').code, false);
  // Enabling it via the workspace flags (from nexus_config.feature_flags) turns
  // it on and unblocks the routes.
  assert.equal(mergeFeatureFlags('owner', { code: true }).code, true);
  assert.equal(
    isWorkspacePathAllowed({ pathname: '/workspace/ws1/code', role: 'owner' }),
    false,
  );
  assert.equal(
    isWorkspacePathAllowed({
      pathname: '/workspace/ws1/code',
      role: 'owner',
      workspaceFlags: { code: true },
    }),
    true,
  );
});

test('isWorkspacePathAllowed blocks disabled routes', () => {
  const allowedChat = isWorkspacePathAllowed({
    pathname: '/workspace/ws1/chat',
    role: 'member',
  });
  const blockedGraph = isWorkspacePathAllowed({
    pathname: '/workspace/ws1/graph',
    role: 'member',
  });

  assert.equal(allowedChat, true);
  assert.equal(blockedGraph, false);
});

test('getFirstAllowedWorkspacePath returns first enabled route', () => {
  const path = getFirstAllowedWorkspacePath({
    workspaceId: 'ws1',
    role: 'member',
  });

  assert.equal(path, '/workspace/ws1/chat');
});
