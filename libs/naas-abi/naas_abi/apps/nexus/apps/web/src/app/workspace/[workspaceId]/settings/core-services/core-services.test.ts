// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AccessLevelsApi, LevelRow, LevelsState } from '@/lib/access-model/access-levels';
import { mount, type Mounted } from '@/lib/testing/mount';
import { pickColumnFilter } from '@/lib/testing/column-filter';
import { CoreServices } from './core-services';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

const SCOPE = 'abi:nexus:organization/acme/nexus:workspace/ws1';
const ACCESS = { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE };
const GRANTS = { id: 'pol_grants', name: 'Analysts grants', owner_scope: SCOPE };

const row = (over: Partial<LevelRow> & Pick<LevelRow, 'name' | 'label'>): LevelRow => ({
  key: `service:${over.name}`,
  kind: 'service',
  level: 'admin',
  choices: ['none', 'read', 'write', 'admin'],
  actions: { read: [`${over.name}:Get`], write: [`${over.name}:Put`], admin: [`${over.name}:Drop`] },
  ...over,
});

const ROWS = [
  row({ name: 'triple_store', label: 'Knowledge graph (triple store)' }),
  row({ name: 'secret', label: 'Secrets', level: 'read', choices: ['none', 'read', 'write'], actions: { read: ['secret:Get'], write: ['secret:Put'] } }),
];

const state = (over: Partial<LevelsState> = {}): LevelsState => ({
  workspace_id: 'ws1',
  kind: 'service',
  mode: 'cap',
  access_policy: ACCESS,
  policy: ACCESS,
  policies: [ACCESS, GRANTS],
  editable: true,
  reason: null,
  rows: ROWS,
  ...over,
});

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const level = (m: Mounted, service: string, value: string) =>
  m.host.querySelector(`tr[data-service="${service}"] [data-level="${value}"]`) as HTMLButtonElement | null;

describe('Settings › Access › Services', () => {
  it('caps each core service for the workspace, apart from the Nexus features, saved at once', async () => {
    const api = {
      read: vi.fn().mockResolvedValue(state()),
      save: vi.fn().mockResolvedValue(state({ rows: [{ ...ROWS[0], level: 'read' }, ROWS[1]] })),
    };
    const m = (mounted = await mount(CoreServices, { workspaceId: 'ws1', api: api as unknown as AccessLevelsApi }));
    await m.flush();
    expect(api.read).toHaveBeenCalledWith('ws1', 'service', null);
    expect(m.host.textContent).toContain('1 capped · 1 open');
    expect(m.host.textContent).toContain('Access › Features');
    expect(level(m, 'triple_store', 'admin')?.getAttribute('aria-checked')).toBe('true');
    // Secrets have no admin level.
    expect(level(m, 'secret', 'admin')).toBeNull();

    await m.click(level(m, 'triple_store', 'read'));
    await m.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', 'service', { 'service:triple_store': 'read' }, null);
    expect(level(m, 'triple_store', 'read')?.getAttribute('aria-checked')).toBe('true');
    expect(m.host.querySelector('[data-services-notice]')?.textContent).toBe('Knowledge graph (triple store): Read.');

    await pickColumnFilter(m, 'access', 'Read');
    expect([...m.host.querySelectorAll('tr[data-service]')].map((r) => r.getAttribute('data-service'))).toEqual([
      'triple_store',
      'secret',
    ]);
  });

  it('edits what another policy grants, picked in the header, and is read-only when IAM says so', async () => {
    const granting = state({ mode: 'grant', policy: GRANTS, rows: ROWS.map((r) => ({ ...r, level: 'none' })) });
    const api = {
      read: vi.fn(async (_ws: string, _kind: string, policy?: string | null) => (policy === 'pol_grants' ? granting : state())),
      save: vi.fn().mockResolvedValue(granting),
    };
    const onPolicyChange = vi.fn();
    const m = (mounted = await mount(CoreServices, {
      workspaceId: 'ws1',
      api: api as unknown as AccessLevelsApi,
      onPolicyChange,
    }));
    await m.flush();
    await m.select(m.host.querySelector('select[data-field="policy"]'), 'pol_grants');
    await m.flush();
    expect(api.read).toHaveBeenLastCalledWith('ws1', 'service', 'pol_grants');
    expect(onPolicyChange).toHaveBeenCalledWith('pol_grants');
    expect(m.host.textContent).toContain('0 granted · 2 none');
    expect(m.host.textContent).toContain('grants whoever holds it');

    await m.unmount();
    api.read.mockResolvedValue(state({ editable: false, reason: 'IAM does not let you change Alpha access.' }));
    const ro = (mounted = await mount(CoreServices, { workspaceId: 'ws1', api: api as unknown as AccessLevelsApi }));
    await ro.flush();
    expect(level(ro, 'secret', 'write')?.disabled).toBe(true);
    expect(ro.host.textContent).toContain('IAM does not let you change Alpha access.');
  });
});
