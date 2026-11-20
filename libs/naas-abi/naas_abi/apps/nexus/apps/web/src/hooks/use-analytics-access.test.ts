// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { createAnalyticsAccessStore } from './use-analytics-access';

const ORG = { kind: 'organization', orgId: 'org-1' } as const;
const WS = { kind: 'workspace', workspaceId: 'ws-1' } as const;
const ORG_ACCESS = '/api/organizations/org-1/analytics/access';
const WS_ACCESS = '/api/workspaces/ws-1/analytics/access';

function fetcher(answers: Record<string, unknown>, seen: string[] = []) {
  return async (url: string) => {
    seen.push(url);
    const answer = answers[url];
    if (answer instanceof Error) throw answer;
    if (typeof answer === 'number') return new Response('{}', { status: answer });
    return new Response(JSON.stringify(answer ?? {}), { status: 200 });
  };
}

describe('analytics access store', () => {
  it('reads each scope once per user, sharing the request in flight', async () => {
    const seen: string[] = [];
    const store = createAnalyticsAccessStore(
      fetcher({ [ORG_ACCESS]: { can_read: true, can_read_conversations: true, timezone: 'Europe/Paris' } }, seen)
    );
    await Promise.all([store.getState().load('u1', ORG), store.getState().load('u1', ORG)]);
    expect(seen).toEqual([ORG_ACCESS]);
    expect(store.getState().entries['organization:org-1']).toEqual({
      status: 'ready',
      access: { can_read: true, can_read_conversations: true, timezone: 'Europe/Paris' },
    });
  });

  it('keeps organizations and workspaces apart', async () => {
    const store = createAnalyticsAccessStore(
      fetcher({ [ORG_ACCESS]: { can_read: true }, [WS_ACCESS]: { can_read: false } })
    );
    await store.getState().load('u1', ORG);
    await store.getState().load('u1', WS);
    expect(store.getState().entries['organization:org-1'].access?.can_read).toBe(true);
    expect(store.getState().entries['workspace:ws-1'].access?.can_read).toBe(false);
  });

  it('reads a refusal (403) as no access, not as an error', async () => {
    const store = createAnalyticsAccessStore(fetcher({ [WS_ACCESS]: 403 }));
    await store.getState().load('u1', WS);
    expect(store.getState().entries['workspace:ws-1']).toEqual({
      status: 'ready',
      access: { can_read: false, can_read_conversations: false, timezone: 'UTC' },
    });
  });

  it('keeps the last answer when a later read fails, and errs with none', async () => {
    const answers: Record<string, unknown> = { [ORG_ACCESS]: { can_read: true } };
    const store = createAnalyticsAccessStore(fetcher(answers));
    await store.getState().load('u1', ORG);
    answers[ORG_ACCESS] = new TypeError('offline');
    await store.getState().load('u1', ORG);
    expect(store.getState().entries['organization:org-1']).toMatchObject({ status: 'ready', access: { can_read: true } });

    const fresh = createAnalyticsAccessStore(fetcher({ [ORG_ACCESS]: 500 }));
    await fresh.getState().load('u1', ORG);
    expect(fresh.getState().entries['organization:org-1']).toEqual({ status: 'error', access: null });
  });

  it('forgets every answer when the user changes', async () => {
    const answers: Record<string, unknown> = { [ORG_ACCESS]: { can_read: true } };
    const store = createAnalyticsAccessStore(fetcher(answers));
    await store.getState().load('u1', ORG);
    answers[ORG_ACCESS] = { can_read: false };
    const pending = store.getState().load('u2', ORG);
    expect(store.getState().userId).toBe('u2');
    expect(store.getState().entries['organization:org-1']).toEqual({ status: 'checking', access: null });
    await pending;
    expect(store.getState().entries['organization:org-1'].access?.can_read).toBe(false);
  });
});
