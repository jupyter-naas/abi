'use client';

import { useMemo } from 'react';
import {
  Button as RACButton,
  Header,
  Menu,
  MenuItem,
  MenuSection,
  MenuTrigger,
  Popover,
} from 'react-aria-components';

import { exportTableData, type TableExportFormat } from '@/lib/export/tableExport';
import type { DataTableColumn } from '@/components/dashboard/DataTable';
import { listHeader, popover } from '@/lib/ariaStyles';
import { useTheme } from '@/lib/theme/ThemeProvider';

type TableExportMenuProps = {
  allRecords: Record<string, unknown>[];
  filteredRecords: Record<string, unknown>[];
  columns: DataTableColumn[];
  fileName?: string;
};

type ExportScope = 'filtered' | 'all';
type ExportActionKey = `${TableExportFormat}-${ExportScope}`;

function formatRowCount(count: number): string {
  return `${count} ligne${count > 1 ? 's' : ''}`;
}

function parseExportActionKey(key: ExportActionKey): {
  format: TableExportFormat;
  scope: ExportScope;
} {
  const [format, scope] = key.split('-') as [TableExportFormat, ExportScope];
  return { format, scope };
}

export function TableExportMenu({
  allRecords,
  filteredRecords,
  columns,
  fileName = 'export',
}: TableExportMenuProps) {
  const { colors } = useTheme();
  const csvSettings = colors.exportFormat.csv;

  const exportColumns = useMemo(
    () => columns.filter((column) => !column.key.startsWith('_')),
    [columns],
  );

  const filteredCount = filteredRecords.length;
  const allCount = allRecords.length;

  async function handleExport(format: TableExportFormat, scope: ExportScope) {
    const records = scope === 'filtered' ? filteredRecords : allRecords;
    await exportTableData(format, records, exportColumns, csvSettings, fileName);
  }

  return (
    <MenuTrigger>
      <RACButton
        className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--text)] transition-colors hover:bg-[var(--accent)] outline-none data-[focus-visible]:ring-2 data-[focus-visible]:ring-[var(--secondary)]"
        isDisabled={allCount === 0}
      >
        <ExportIcon />
        Export
        <span aria-hidden className="text-[10px] text-[var(--text-muted)]">
          ▾
        </span>
      </RACButton>
      <Popover className={`${popover} min-w-[15rem] p-1`} offset={4}>
        <Menu
          className="outline-none"
          onAction={(key) => {
            const { format, scope } = parseExportActionKey(key as ExportActionKey);
            void handleExport(format, scope);
          }}
        >
          <MenuSection>
            <Header className={listHeader}>
              Filtres appliqués · {formatRowCount(filteredCount)}
            </Header>
            <MenuItem
              id="csv-filtered"
              isDisabled={filteredCount === 0}
              className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40 data-[focused]:bg-[var(--accent)] data-[hovered]:bg-[var(--accent)]"
            >
              CSV
            </MenuItem>
            <MenuItem
              id="xlsx-filtered"
              isDisabled={filteredCount === 0}
              className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40 data-[focused]:bg-[var(--accent)] data-[hovered]:bg-[var(--accent)]"
            >
              Excel (.xlsx)
            </MenuItem>
          </MenuSection>
          <MenuSection>
            <Header className={listHeader}>Toutes les lignes · {formatRowCount(allCount)}</Header>
            <MenuItem
              id="csv-all"
              isDisabled={allCount === 0}
              className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40 data-[focused]:bg-[var(--accent)] data-[hovered]:bg-[var(--accent)]"
            >
              CSV
            </MenuItem>
            <MenuItem
              id="xlsx-all"
              isDisabled={allCount === 0}
              className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-40 data-[focused]:bg-[var(--accent)] data-[hovered]:bg-[var(--accent)]"
            >
              Excel (.xlsx)
            </MenuItem>
          </MenuSection>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}

function ExportIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className="shrink-0"
    >
      <path
        d="M10 3.5v9M6.75 9.25 10 12.5l3.25-3.25"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4.5 14.5v1.75A1.75 1.75 0 0 0 6.25 18h7.5a1.75 1.75 0 0 0 1.75-1.75V14.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
