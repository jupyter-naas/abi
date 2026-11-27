// @vitest-environment jsdom
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { DatasetInfo } from '@/stores/datasets';

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/workspace/ws-1/datasets',
  useRouter: () => nav,
}));

import { useDatasetsStore } from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';
import { DatasetsNamespaceGroups, filterDatasets } from './datasets-section';

const table = (namespace: string, name: string, columns: string[] = []): DatasetInfo => ({
  namespace,
  name,
  columns: columns.map((column) => ({ name: column })) as DatasetInfo['columns'],
  partitions: [],
  primary_key: [],
  snapshot_id: 1,
  location: '',
});
const TABLES = [
  table('finance', 'invoices', ['amount', 'customer']),
  table('finance', 'budgets'),
  table('hr', 'employees', ['salary']),
  table('sales', 'orders', ['customer']),
];

describe('filterDatasets', () => {
  it('keeps the namespaces picked, every one when none is', () => {
    expect(filterDatasets(TABLES, [], '').length).toBe(4);
    expect(filterDatasets(TABLES, ['finance', 'hr'], '').map((t) => t.name)).toEqual(['invoices', 'budgets', 'employees']);
  });

  it('searches a table by its name, its namespace or a column, every word', () => {
    expect(filterDatasets(TABLES, [], 'customer').map((t) => t.name)).toEqual(['invoices', 'orders']);
    expect(filterDatasets(TABLES, [], 'hr').map((t) => t.name)).toEqual(['employees']);
    expect(filterDatasets(TABLES, ['sales'], 'customer orders').map((t) => t.name)).toEqual(['orders']);
  });
});

let mounted: Mounted | null = null;

describe('Datasets in the sidebar', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-1' });
    useDatasetsStore.setState({
      datasets: TABLES,
      loading: false,
      error: null,
      collapsedNamespaces: [],
      toggleNamespace: vi.fn(),
      fetchDatasets: vi.fn(async () => undefined),
    } as never);
  });
  afterEach(async () => {
    await mounted?.unmount();
    mounted = null;
  });

  it('opens on Dashboard, with Ontology\'s filters, every namespace open, and a search that keeps what it finds', async () => {
    mounted = await mount(DatasetsNamespaceGroups, {});
    const dashboard = mounted.host.querySelector('button.shell-sidebar-home')!;
    expect(dashboard.textContent).toBe('Dashboard');
    expect(dashboard.getAttribute('aria-current')).toBe('page');
    expect(mounted.host.querySelector('.search-picker-trigger')?.textContent).toContain('All namespaces');
    const rows = () => [...mounted!.host.querySelectorAll('.datasets-section-row')].map((r) => r.querySelector('.datasets-section-row__label')?.textContent);
    // Every namespace open by default.
    expect(rows()).toEqual(['invoices', 'budgets', 'employees', 'orders']);
    const search = mounted.host.querySelector<HTMLInputElement>('input[aria-label="Search tables"]')!;
    expect(search.placeholder).toBe('Search tables…');
    await mounted.type(search, 'customer');
    expect(rows()).toEqual(['invoices', 'orders']);
    await mounted.type(search, 'nothing-like-it');
    expect(mounted.host.textContent).toContain('No table matches');
    await act(async () => undefined);
  });

  it('lists the tables A–Z, and a namespace\'s name opens its gallery', async () => {
    mounted = await mount(DatasetsNamespaceGroups, {});
    const az = [...mounted.host.querySelectorAll('[aria-label="Sidebar view"] button')].find((b) => b.textContent === 'A–Z')!;
    await mounted.click(az);
    const rows = [...mounted.host.querySelectorAll('.datasets-section-row__label')].map((r) => r.textContent);
    expect(rows).toEqual(['budgets', 'employees', 'invoices', 'orders']);
    const namespaces = [...mounted.host.querySelectorAll('[aria-label="Sidebar view"] button')].find((b) => b.textContent === 'Namespaces')!;
    await mounted.click(namespaces);
    await mounted.click(mounted.host.querySelector('[data-namespace-gallery="hr"]'));
    expect(nav.push).toHaveBeenCalledWith('/workspace/ws-1/datasets/hr');
  });
});
