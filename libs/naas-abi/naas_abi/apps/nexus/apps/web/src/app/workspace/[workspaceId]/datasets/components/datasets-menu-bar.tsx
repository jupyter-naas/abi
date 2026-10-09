'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';
import { useDatasetsStore } from '@/stores/datasets';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * The Datasets section's app menu bar, sitting in the topnav through
 * `Header nav=`. File → Refresh reloads the table list in the section.
 */
export function DatasetsMenuBar() {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const loading = useDatasetsStore((s) => s.loading);
  const fetchDatasets = useDatasetsStore((s) => s.fetchDatasets);

  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Datasets menus" data-testid="datasets-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Datasets</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="datasets-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item
              className={APP_MENU_ROW}
              disabled={loading || !workspaceId}
              onSelect={() => { void fetchDatasets(workspaceId); }}
              data-testid="datasets-menuitem-refresh"
            >
              {loading ? 'Refreshing…' : 'Refresh'}
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
