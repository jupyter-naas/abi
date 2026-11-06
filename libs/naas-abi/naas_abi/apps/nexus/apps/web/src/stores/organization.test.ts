import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.fn();

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
vi.mock('@/stores/auth', () => ({ authFetch: (...args: unknown[]) => authFetch(...args) }));
vi.mock('@/lib/org-branding', () => ({ invalidateOrgBranding: () => undefined }));

import { useOrganizationStore } from './organization';

const answer = (status: number, body: unknown) =>
  ({ ok: status < 400, status, json: () => Promise.resolve(body) }) as Response;

const sent = () => JSON.parse(authFetch.mock.calls.at(-1)?.[1]?.body as string);

describe('an invitation to an organization', () => {
  beforeEach(() => {
    authFetch.mockReset();
    authFetch.mockResolvedValue(answer(200, { id: 'm1', organization_id: 'acme', user_id: 'usr_bob', role: 'member' }));
  });

  it('carries the picked policies as policy_ids, with the workspace they attach at', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', {
      email: 'bob@example.com',
      role: 'member',
      workspaceId: 'ws-1',
      workspaceRole: 'member',
      policyIds: ['pol_features', 'pol_graph'],
    });
    expect(authFetch.mock.calls.at(-1)?.[0]).toBe('/api/organizations/acme/members/invite');
    expect(sent()).toMatchObject({
      email: 'bob@example.com',
      role: 'member',
      workspace_id: 'ws-1',
      policy_ids: ['pol_features', 'pol_graph'],
    });
  });

  it('names no policy when none is picked', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', role: 'member', policyIds: [] });
    expect(sent()).not.toHaveProperty('policy_ids');
  });

  it('says what IAM refused', async () => {
    authFetch.mockResolvedValue(answer(403, { detail: 'You cannot grant what you do not hold: nexus:UseFeature on graph' }));
    await expect(
      useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', role: 'member', policyIds: ['pol_graph'] }),
    ).rejects.toThrow('You cannot grant what you do not hold');
  });
});
