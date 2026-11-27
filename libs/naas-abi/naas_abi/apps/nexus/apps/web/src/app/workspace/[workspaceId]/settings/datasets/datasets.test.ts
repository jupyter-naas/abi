// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { DatasetsOfferApi } from './datasets-api';
import { changesFrom, datasetExportRow, type DatasetRow, type DatasetsState } from './datasets-model';
import { DatasetsOffer } from './datasets';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

const SCOPE = 'abi:nexus:organization/acme/nexus:workspace/ws1';

function row(over: Partial<DatasetRow> & Pick<DatasetRow, 'namespace'>): DatasetRow {
  return { tables: 1, available: true, offered: true, closed_above: false, editable: true, reason: null, ...over };
}

function state(rows: DatasetRow[], over: Partial<DatasetsState> = {}): DatasetsState {
  return {
    workspace_id: 'ws1',
    scope: SCOPE,
    access_policy: { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE },
    ceiling: { id: 'pol_org', name: 'Acme access', owner_scope: 'abi:nexus:organization/acme' },
    editable: true,
    rows,
    error: null,
    ...over,
  };
}

const BEFORE = state([
  row({ namespace: 'finance', tables: 12 }),
  row({ namespace: 'hr', tables: 4, offered: false }),
  row({
    namespace: 'payroll',
    tables: 2,
    offered: false,
    closed_above: true,
    editable: false,
    reason: 'Not offered by Acme access: open it there first.',
  }),
]);

function fakeApi(after?: DatasetsState) {
  return { read: vi.fn().mockResolvedValue(BEFORE), save: vi.fn().mockResolvedValue(after ?? BEFORE) };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(api: ReturnType<typeof fakeApi>, target = 'ws1') {
  mounted = await mount(DatasetsOffer, { target, api: api as unknown as DatasetsOfferApi });
  await mounted.flush();
  return mounted;
}

const box = (m: Mounted, namespace: string) =>
  m.host.querySelector(`tr[data-namespace="${namespace}"] input[data-offered]`) as HTMLInputElement | null;
const saveButton = (m: Mounted) => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;

describe('DatasetsOffer', () => {
  it('lists each namespace, its datasets and whether the workspace uses it', async () => {
    const m = await render(fakeApi());
    expect([...m.host.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual([
      'Namespace',
      'Datasets',
      'Offered',
    ]);
    expect([...m.host.querySelectorAll('tr[data-namespace]')].map((tr) => tr.getAttribute('data-namespace'))).toEqual([
      'finance',
      'hr',
      'payroll',
    ]);
    expect(box(m, 'finance')?.checked).toBe(true);
    expect(box(m, 'hr')?.checked).toBe(false);
    // One total in the badge, no count above the search.
    expect(m.host.textContent).toContain('3 namespaces');
    expect(m.host.textContent).not.toContain('not offered ·');
    // The description fits one line and links "<W> access".
    expect(m.host.querySelector('a[href*="pol_access"]')?.textContent).toBe('Alpha access');
    // Reopening is the platform admin's: the legend says so.
    expect(m.host.querySelector('[data-datasets-legend]')?.textContent).toContain('platform admin');
    expect(saveButton(m).disabled).toBe(true);
  });

  it('keeps what the organization closes read-only, with why', async () => {
    const m = await render(fakeApi());
    expect(box(m, 'payroll')?.disabled).toBe(true);
    expect(m.host.querySelector('tr[data-namespace="payroll"]')?.textContent).toContain('Not offered by Acme access');
  });

  it('closes and reopens namespaces in one save', async () => {
    const after = state([row({ namespace: 'finance', tables: 12, offered: false }), ...BEFORE.rows.slice(1)]);
    const api = fakeApi(after);
    const m = await render(api);
    await m.click(box(m, 'finance'));
    await m.click(box(m, 'hr'));
    expect(saveButton(m).disabled).toBe(false);
    await m.click(saveButton(m));
    await m.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', { finance: false, hr: true });
    expect(box(m, 'finance')?.checked).toBe(false);
    expect(saveButton(m).disabled).toBe(true);
  });

  it('says what IAM refused and keeps the drafts', async () => {
    const api = fakeApi();
    api.save.mockRejectedValue(new Error('only the platform admin lifts its Denies'));
    const m = await render(api);
    await m.click(box(m, 'hr'));
    await m.click(saveButton(m));
    await m.flush();
    expect(m.host.textContent).toContain('only the platform admin lifts its Denies');
    expect(box(m, 'hr')?.checked).toBe(true);
    expect(saveButton(m).disabled).toBe(false);
  });

  it('says so when the deployment lists no dataset', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue(state([], { error: 'This deployment lists no dataset.' }));
    const m = await render(api);
    expect(m.host.textContent).toContain('This deployment lists no dataset.');
  });

  it('on an organization, edits "<O> access" for every workspace', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue({ ...BEFORE, ceiling: null, access_policy: { id: 'pol_org', name: 'Acme access', owner_scope: 'abi:' } });
    const m = await render(api, 'org:acme');
    expect(api.read).toHaveBeenCalledWith('org:acme');
    expect(m.host.textContent).toContain('workspaces of this organization');
  });
});

describe('the datasets model', () => {
  it('sends only what changed, and exports as the table shows', () => {
    expect(changesFrom(BEFORE.rows, { finance: true, hr: true })).toEqual({ hr: true });
    expect(datasetExportRow(BEFORE.rows[2])).toEqual(['payroll', '2', 'No', 'Yes']);
  });
});
