'use client';

import { Columns3, LayoutGrid, List, Table2 } from 'lucide-react';
import { ViewBar as DatabaseViewBar, type ViewTypeDef } from '@/components/database-view/view-bar';
import type { AppViewsApi } from './use-app-views';
import { APPS_SCHEMA, VIEW_TYPE_LABELS, type AppRecord, type ViewType } from './types';

const VIEW_TYPES: ViewTypeDef<ViewType>[] = [
  { type: 'gallery', label: VIEW_TYPE_LABELS.gallery, icon: LayoutGrid },
  { type: 'table', label: VIEW_TYPE_LABELS.table, icon: Table2 },
  { type: 'list', label: VIEW_TYPE_LABELS.list, icon: List },
  { type: 'board', label: VIEW_TYPE_LABELS.board, icon: Columns3 },
];

export function ViewBar({
  api,
  records,
  search,
  onSearchChange,
  count,
}: {
  api: AppViewsApi;
  /** Unfiltered rows — filter menus offer the values that actually exist. */
  records: AppRecord[];
  search: string;
  onSearchChange: (value: string) => void;
  count: number;
}) {
  return (
    <DatabaseViewBar
      api={api}
      schema={APPS_SCHEMA}
      viewTypes={VIEW_TYPES}
      records={records}
      search={search}
      onSearchChange={onSearchChange}
      count={count}
      countLabel={(n) => `${n} ${n === 1 ? 'app' : 'apps'}`}
      defaultFilterProperty="category"
      groupedTypes={['board']}
      defaultGroupBy="module"
    />
  );
}
