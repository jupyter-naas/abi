'use client';

import { create } from 'zustand';
import type { ColumnFilterState } from '@/lib/graph-query/filters';
import { onPageStateOwnerChange } from '@/lib/page-state';

export type TablesColumnId = 'table' | 'section' | 'description' | 'rows' | 'columns';
export type SortDir = 'asc' | 'desc';

/**
 * How the Nexus tables page was left: search, column filters, sort and the open
 * schema. It lives in memory for the tab, so a table's close button brings the
 * page back as it was. It also keeps each table's label as the API gave it, for
 * the phone's header. Like every page state (`lib/page-state.ts`), it belongs to the
 * session: another account, sign-out or a view (View as) starts it afresh.
 */
interface TablesViewState {
  search: string;
  columnFilters: Partial<Record<TablesColumnId, ColumnFilterState>>;
  sortKey: TablesColumnId | null;
  sortDir: SortDir;
  openTable: string | null;
  /** Table name → label, from the pages that loaded them. */
  labels: Record<string, string>;
  setSearch: (search: string) => void;
  setColumnFilters: (
    next: (
      current: Partial<Record<TablesColumnId, ColumnFilterState>>
    ) => Partial<Record<TablesColumnId, ColumnFilterState>>
  ) => void;
  setSort: (sortKey: TablesColumnId | null, sortDir: SortDir) => void;
  setOpenTable: (name: string | null) => void;
  rememberLabels: (tables: readonly { name: string; label: string }[]) => void;
}

const LEFT_AS_NEW = {
  search: '',
  columnFilters: {},
  sortKey: null,
  sortDir: 'asc',
  openTable: null,
  labels: {},
} satisfies Partial<TablesViewState>;

export const useTablesView = create<TablesViewState>((set) => ({
  ...LEFT_AS_NEW,
  setSearch: (search) => set({ search }),
  setColumnFilters: (next) => set((state) => ({ columnFilters: next(state.columnFilters) })),
  setSort: (sortKey, sortDir) => set({ sortKey, sortDir }),
  setOpenTable: (openTable) => set({ openTable }),
  rememberLabels: (tables) =>
    set((state) => ({
      labels: {
        ...state.labels,
        ...Object.fromEntries(tables.map((table) => [table.name, table.label])),
      },
    })),
}));

onPageStateOwnerChange(() => useTablesView.setState(LEFT_AS_NEW));
