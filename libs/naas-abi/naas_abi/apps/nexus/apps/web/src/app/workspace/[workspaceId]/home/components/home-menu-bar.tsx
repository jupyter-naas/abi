'use client';

import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';
import type { HomeFileMenuRow } from '../home-desk-nav';

/**
 * The Home section's app menu bar, sitting in the topnav through
 * `Header nav=`. File lists the same destinations as the desk; Edit holds
 * wallpaper and other home chrome.
 */
export function HomeMenuBar({
  fileMenuRows,
  canEditBackground,
  onEditBackground,
}: {
  fileMenuRows: HomeFileMenuRow[];
  /** Workspace owners and admins only; others see the item greyed. */
  canEditBackground: boolean;
  onEditBackground: () => void;
}) {
  const fileItems: MenuEntry[] = fileMenuRows.some((row) => row.kind === 'item')
    ? fileMenuRows.map((row) =>
        row.kind === 'separator' ? row : { id: row.id, label: row.label, onSelect: row.navigate })
    : [{ id: 'no-items', label: 'No items', disabled: true }];

  return (
    <MenuBar label="Home menus" title="Home" testId="home-menu-bar">
      <Menu label="File" testId="home-menu-file" items={fileItems} />
      <Menu
        label="Edit"
        testId="home-menu-edit"
        itemTestIdPrefix="home-menuitem-"
        items={[{
          id: 'desktop-wallpaper',
          label: 'Desktop wallpaper…',
          disabled: !canEditBackground,
          title: canEditBackground ? undefined : 'Only workspace admins can change the desktop wallpaper',
          onSelect: onEditBackground,
        }]}
      />
    </MenuBar>
  );
}
