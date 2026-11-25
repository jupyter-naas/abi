'use client';

import { Menu, MenuBar } from '@/components/ui/menu';
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
    <MenuBar label="Datasets menus" title="Datasets" testId="datasets-menu-bar">
      <Menu
        label="File"
        testId="datasets-menu-file"
        itemTestIdPrefix="datasets-menuitem-"
        items={[{
          id: 'refresh',
          label: loading ? 'Refreshing…' : 'Refresh',
          disabled: loading || !workspaceId,
          onSelect: () => void fetchDatasets(workspaceId),
        }]}
      />
    </MenuBar>
  );
}
