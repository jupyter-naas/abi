'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown, Download, RefreshCw } from 'lucide-react';
import type { UsersExportFormat } from './users-table-export';

/**
 * Users › Reload, at an organization or the platform (a workspace's header has the settings
 * Reload): read the table again.
 */
export function UsersReloadButton({ onReload, busy = false }: { onReload: () => void; busy?: boolean }) {
  return (
    <button
      type="button"
      className="org-settings-users-secondary-button"
      onClick={onReload}
      disabled={busy}
      title="Reload"
      aria-label="Reload"
      data-action="reload"
    >
      <RefreshCw size={16} className={busy ? 'animate-spin' : undefined} />
    </button>
  );
}

/** Users › Export: the rows the table shows (search and filters applied), as CSV or Excel. */
export function UsersExportMenu({
  onExport,
  disabled = false,
}: {
  onExport: (format: UsersExportFormat) => void;
  disabled?: boolean;
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button type="button" className="org-settings-users-secondary-button" data-action="export" disabled={disabled}>
          <Download size={16} />
          Export
          <ChevronDown size={14} />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={4} className="org-settings-users-export-menu">
          <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => onExport('csv')}>
            CSV
          </DropdownMenu.Item>
          <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => onExport('xlsx')}>
            Excel (.xlsx)
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
