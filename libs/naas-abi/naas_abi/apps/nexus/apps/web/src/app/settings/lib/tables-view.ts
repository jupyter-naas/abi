'use client';

import { create } from 'zustand';
import type { ColumnFilterState } from '@/lib/graph-query/filters';

export type TablesColumnId = 'table' | 'section' | 'description' | 'rows' | 'columns';
export type SortDir = 'asc' | 'desc';

/**
 * How the Nexus tables page was left: search, column filters, sort and the open
 * schema. It lives in memory for the tab, so a table's close button brings the
 * page back as it was.
 */
interface TablesViewState {
  search: string;
  columnFilters: Partial<Record<TablesColumnId, ColumnFilterState>>;
  sortKey: TablesColumnId | null;
  sortDir: SortDir;
  openTable: string | null;
  setSearch: (search: string) => void;
  setColumnFilters: (
    next: (
      current: Partial<Record<TablesColumnId, ColumnFilterState>>
    ) => Partial<Record<TablesColumnId, ColumnFilterState>>
  ) => void;
  setSort: (sortKey: TablesColumnId | null, sortDir: SortDir) => void;
  setOpenTable: (name: string | null) => void;
}

export const useTablesView = create<TablesViewState>((set) => ({
  search: '',
  columnFilters: {},
  sortKey: null,
  sortDir: 'asc',
  openTable: null,
  setSearch: (search) => set({ search }),
  setColumnFilters: (next) => set((state) => ({ columnFilters: next(state.columnFilters) })),
  setSort: (sortKey, sortDir) => set({ sortKey, sortDir }),
  setOpenTable: (openTable) => set({ openTable }),
}));
