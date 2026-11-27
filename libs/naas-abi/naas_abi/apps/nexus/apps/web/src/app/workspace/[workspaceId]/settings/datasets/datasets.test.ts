// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { DatasetsOfferApi } from './datasets-api';
import { bulkChanges, changesFrom, datasetExportRow, type DatasetRow, type DatasetsState } from './datasets-model';
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
  row({ namespace: 'finance', tables: 12, datasets: ['budgets', 'invoices'] }),
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
const notice = (m: Mounted) => m.host.querySelector('[data-datasets-notice]')?.textContent ?? null;
const confirmButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === label)!;

describe('DatasetsOffer', () => {
  it('lists each namespace, its datasets and whether the workspace uses it', async () => {
    const m = await render(fakeApi());
    // The select column first (batch changes), then the table's own.
    expect([...m.host.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual([
      '',
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
    // No legend above the table: the page's description says what it is.
    expect(m.host.querySelector('[data-datasets-legend]')).toBeNull();
    // A table of switches: each change is saved at once, no Save nor Discard.
    expect(m.host.querySelector('[data-action="save"]')).toBeNull();
    expect(m.host.querySelector('[data-action="discard"]')).toBeNull();
  });

  it('keeps what the organization closes read-only, with why', async () => {
    const m = await render(fakeApi());
    expect(box(m, 'payroll')?.disabled).toBe(true);
    expect(m.host.querySelector('tr[data-namespace="payroll"]')?.textContent).toContain('Not offered by Acme access');
  });

  it('closes a namespace at once, and says so', async () => {
    const after = state([row({ namespace: 'finance', tables: 12, offered: false }), ...BEFORE.rows.slice(1)]);
    const api = fakeApi(after);
    const m = await render(api);
    await m.click(box(m, 'finance'));
    await m.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', { finance: false }, null);
    expect(box(m, 'finance')?.checked).toBe(false);
    expect(notice(m)).toBe('finance: not offered.');
  });

  it('offers or takes back the namespaces selected in one save, the read-only ones counted', async () => {
    const api = fakeApi();
    const m = await render(api);
    await m.click(m.host.querySelector('thead input[data-action="select-all"]'));
    // payroll is closed above: it cannot be selected.
    expect(m.host.querySelector('[data-bulk-bar]')?.textContent).toContain('2 namespaces selected');
    await m.click(m.host.querySelector('[data-bulk-bar] [data-bulk-action="off"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Take back 2 namespaces?');
    await m.click(confirmButton('Take back'));
    await m.flush();
    // hr is already not offered: one change only.
    expect(api.save).toHaveBeenCalledWith('ws1', { finance: false }, null);
    expect(notice(m)).toBe('1 namespace taken back.');
  });

  it('says what IAM refused, and the switch stays as it was', async () => {
    const api = fakeApi();
    api.save.mockRejectedValue(new Error('only the platform admin lifts its Denies'));
    const m = await render(api);
    await m.click(box(m, 'hr'));
    await m.flush();
    expect(m.host.textContent).toContain('only the platform admin lifts its Denies');
    expect(box(m, 'hr')?.checked).toBe(false);
  });

  it('says so when the deployment lists no dataset', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue(state([], { error: 'This deployment lists no dataset.' }));
    const m = await render(api);
    expect(m.host.textContent).toContain('This deployment lists no dataset.');
  });

  it('reads and writes the policy picked in the Settings column, and names it', async () => {
    const api = fakeApi();
    const grants = { id: 'pol_g', name: 'Analysts grants', owner_scope: SCOPE };
    api.read.mockResolvedValue({ ...BEFORE, policy: grants });
    api.save.mockResolvedValue({ ...BEFORE, policy: grants });
    mounted = await mount(DatasetsOffer, { target: 'ws1', policyId: 'pol_g', api: api as unknown as DatasetsOfferApi });
    await mounted.flush();
    expect(api.read).toHaveBeenCalledWith('ws1', 'pol_g');
    expect(mounted.host.querySelector('a[href*="pol_g"]')?.textContent).toBe('Analysts grants');
    await mounted.click(box(mounted, 'finance'));
    await mounted.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', { finance: false }, 'pol_g');
  });

  it('on an organization, edits "<O> access" for every workspace', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue({ ...BEFORE, ceiling: null, access_policy: { id: 'pol_org', name: 'Acme access', owner_scope: 'abi:' } });
    const m = await render(api, 'org:acme');
    expect(api.read).toHaveBeenCalledWith('org:acme', null);
    expect(m.host.textContent).toContain('workspaces of this organization');
  });
});

describe('the datasets model', () => {
  it('sends only what changed, and exports as the table shows', () => {
    expect(changesFrom(BEFORE.rows, { finance: true, hr: true })).toEqual({ hr: true });
    expect(datasetExportRow(BEFORE.rows[2])).toEqual(['payroll', '2', 'No', 'Yes']);
  });

  it('a batch change names the editable rows it changes', () => {
    expect(bulkChanges(BEFORE.rows, ['finance', 'hr', 'payroll'], true)).toEqual({ hr: true });
    expect(bulkChanges(BEFORE.rows, ['finance', 'hr', 'payroll'], false)).toEqual({ finance: false });
  });
});

let unfoldMounted: Mounted | null = null;

describe('Settings › Datasets, a namespace unfolds its datasets', () => {
  afterEach(async () => {
    await unfoldMounted?.unmount();
    unfoldMounted = null;
  });

  it('as a module its items: folded at first, unfolded from its name, a search opens what it finds', async () => {
    const api = { read: vi.fn(async () => BEFORE), save: vi.fn() } as unknown as DatasetsOfferApi;
    unfoldMounted = await mount(DatasetsOffer, { target: 'ws1', api });
    await unfoldMounted.flush();
    const datasets = () => [...unfoldMounted!.host.querySelectorAll('[data-namespace-dataset]')].map((r) => r.textContent);
    expect(datasets()).toEqual([]);
    const name = unfoldMounted.host.querySelector('[data-namespace="finance"] button[data-action="datasets"]')!;
    expect(name.getAttribute('aria-expanded')).toBe('false');
    await unfoldMounted.click(name);
    expect(datasets()).toEqual(['budgets', 'invoices']);
    // A namespace without datasets named has nothing to unfold.
    expect(unfoldMounted.host.querySelector('[data-namespace="hr"] button[data-action="datasets"]')).toBeNull();
    await unfoldMounted.click(name);
    expect(datasets()).toEqual([]);
    await unfoldMounted.type(unfoldMounted.host.querySelector('input[type="search"]') as HTMLInputElement, 'invoices');
    expect(datasets()).toEqual(['budgets', 'invoices']);
    expect([...unfoldMounted.host.querySelectorAll('tr[data-namespace]')].map((r) => r.getAttribute('data-namespace'))).toEqual(['finance']);
  });
});
