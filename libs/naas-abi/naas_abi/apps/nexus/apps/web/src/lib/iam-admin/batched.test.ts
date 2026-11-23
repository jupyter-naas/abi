/**
 * Batched Settings reads (#1608), through the real client over a fake API: the Groups list
 * with every member count in one request per page of at most `GROUPS_PAGE_MAX`, and the
 * attachments of a person's groups in one request per `MAX_PRINCIPALS_PER_READ`.
 */
import { describe, expect, it } from 'vitest';
import { createIamAdminApi } from './api';
import { GROUPS_PAGE_MAX, MAX_PRINCIPALS_PER_READ, attachmentsByPrincipal, listAllGroups } from './batched';

type Call = { url: URL };

function fakeApi(answer: (url: URL) => { status?: number; body: unknown }) {
  const calls: Call[] = [];
  const fetcher = async (input: string) => {
    const url = new URL(input, 'http://api');
    calls.push({ url });
    const { status = 200, body } = answer(url);
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  };
  return { api: createIamAdminApi(fetcher), calls };
}

const group = (i: number) => ({
  id: `grp_${String(i).padStart(4, '0')}`,
  kind: 'group',
  status: 'active',
  name: `G${i}`,
  email: null,
  display_name: null,
  provider: null,
  org: null,
  owner_id: null,
  created_at: null,
  owner_scope: 'abi:',
  member_count: i % 7,
});

/** `total` groups served in pages, as IAM pages them (by id, `after` the last one sent). */
function groupsApi(total: number) {
  const all = Array.from({ length: total }, (_, i) => group(i));
  return fakeApi((url) => {
    const limit = Number(url.searchParams.get('limit') ?? 100);
    const after = url.searchParams.get('after');
    const start = after ? all.findIndex((g) => g.id === after) + 1 : 0;
    const items = all.slice(start, start + limit);
    const more = start + limit < all.length;
    return { body: { items, next_after: more ? items[items.length - 1].id : null } };
  });
}

describe('listAllGroups', () => {
  it('reads 500 groups and their member counts in one request, no detail per group', async () => {
    const { api, calls } = groupsApi(500);
    const groups = await listAllGroups(api, 'abi:nexus:organization/acme');
    expect(groups).toHaveLength(500);
    expect(groups[3].member_count).toBe(3);
    expect(calls).toHaveLength(1);
    const asked = calls[0].url;
    expect(asked.pathname).toBe('/api/iam/admin/groups');
    expect(asked.searchParams.get('member_counts')).toBe('true');
    expect(asked.searchParams.get('limit')).toBe(String(GROUPS_PAGE_MAX));
    expect(asked.searchParams.get('scope')).toBe('abi:nexus:organization/acme');
  });

  it('follows the pages past the bound, each group once, in the API’s order', async () => {
    const { api, calls } = groupsApi(1201);
    const groups = await listAllGroups(api);
    expect(calls).toHaveLength(3);
    expect(groups.map((g) => g.id)).toEqual(Array.from({ length: 1201 }, (_, i) => group(i).id));
    expect(calls[1].url.searchParams.get('after')).toBe(group(GROUPS_PAGE_MAX - 1).id);
  });

  it('stops on a cursor that does not move rather than reading forever', async () => {
    const { api, calls } = fakeApi(() => ({ body: { items: [group(1)], next_after: 'grp_0001' } }));
    const groups = await listAllGroups(api);
    expect(calls).toHaveLength(2);
    expect(groups.map((g) => g.id)).toEqual(['grp_0001']);
  });

  it('passes a refusal on, as the list did', async () => {
    const { api } = fakeApi(() => ({ status: 403, body: { detail: 'Not yours' } }));
    await expect(listAllGroups(api)).rejects.toThrow('Not yours');
  });
});

describe('attachmentsByPrincipal', () => {
  const row = (principal: string, policy: string) => ({
    id: `${principal}-${policy}`,
    policy_id: policy,
    policy_name: policy,
    policy_owner_scope: 'abi:',
    principal_id: principal,
    principal: null,
    scope: null,
    created_at: null,
  });
  const attachmentsApi = () =>
    fakeApi((url) => ({
      body: { items: url.searchParams.getAll('principal_id').flatMap((p) => [row(p, 'pol_a'), row(p, 'pol_b')]) },
    }));

  it('reads 60 groups’ attachments in one request, each group’s rows under it', async () => {
    const { api, calls } = attachmentsApi();
    const ids = Array.from({ length: 60 }, (_, i) => `grp_${i}`);
    const found = await attachmentsByPrincipal(api, ids);
    expect(calls).toHaveLength(1);
    expect(calls[0].url.searchParams.getAll('principal_id')).toEqual(ids);
    expect(found.get('grp_7')?.items.map((a) => a.policy_id)).toEqual(['pol_a', 'pol_b']);
  });

  it('splits more principals than one read may name, and keeps the scope', async () => {
    const { api, calls } = attachmentsApi();
    const ids = Array.from({ length: MAX_PRINCIPALS_PER_READ + 1 }, (_, i) => `grp_${i}`);
    const found = await attachmentsByPrincipal(api, ids, 'abi:nexus:organization/acme');
    expect(calls).toHaveLength(2);
    expect(calls.map((c) => c.url.searchParams.getAll('principal_id').length)).toEqual([MAX_PRINCIPALS_PER_READ, 1]);
    for (const c of calls) expect(c.url.searchParams.get('scope')).toBe('abi:nexus:organization/acme');
    expect(found.size).toBe(MAX_PRINCIPALS_PER_READ + 1);
  });

  it('asks nothing for no principal, and says which ones a failed read leaves out', async () => {
    const none = attachmentsApi();
    expect((await attachmentsByPrincipal(none.api, [])).size).toBe(0);
    expect(none.calls).toHaveLength(0);
    const { api } = fakeApi(() => ({ status: 503, body: { detail: 'IAM is down' } }));
    const found = await attachmentsByPrincipal(api, ['grp_1', 'grp_2']);
    expect(found.get('grp_1')?.error?.message).toBe('IAM is down');
    expect(found.get('grp_2')?.items).toEqual([]);
  });
});
