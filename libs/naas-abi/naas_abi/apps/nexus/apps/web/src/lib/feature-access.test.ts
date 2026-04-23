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
  assert.equal(flags.knowledge, false);
  assert.equal(flags.settings, false);
});

test('mergeFeatureFlags applies workspace overrides', () => {
  const flags = mergeFeatureFlags('member', { knowledge: true, chat: false });

  assert.equal(flags.chat, false);
  assert.equal(flags.files, true);
  assert.equal(flags.knowledge, true);
});

test('guard maps workspace paths to features', () => {
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/chat'), 'chat');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/graph'), 'knowledge');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/settings/agents'), 'agents');
  assert.equal(getFeatureForWorkspacePath('/workspace/ws1/help'), 'settings');
});

test('guard supports org-scoped rewritten routes', () => {
  assert.equal(getFeatureForWorkspacePath('/org/acme/workspace/ws1/chat'), 'chat');
  assert.equal(getFeatureForWorkspacePath('/org/acme/workspace/ws1/lab'), 'agents');
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
