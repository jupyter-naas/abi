'use client';

import type { ReactNode } from 'react';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';

export interface AppsMenuBarProps {
  /** File → New App. Omitted or disabled, the item greys out rather than vanishing. */
  onNewApp?: () => void;
  newAppDisabled?: boolean;
  /** Extra File entries appended under a separator (the open app adds "All apps"). */
  fileExtras?: MenuEntry[];
  /** Entries for an Edit menu. Omitted or empty, no Edit menu is drawn. */
  editItems?: MenuEntry[];
  /** Keep Edit on the bar but inert — the section still reads the same. */
  editDisabled?: boolean;
  editDisabledTitle?: string;
  /** Rendered ahead of the "Apps" label — the editor's back arrow. */
  leading?: ReactNode;
  /** Rendered after the menus: status text, branch name, unsaved marker. */
  trailing?: ReactNode;
}

/**
 * The Apps section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as `SlidesMenuBar` / `DocumentsMenuBar` /
 * the Ontology bar: a section label, then File — so creating an app is a
 * menu entry like every other section's "New …", not a coloured button
 * floating in the top-right corner.
 */
export function AppsMenuBar({
  onNewApp,
  newAppDisabled,
  fileExtras,
  editItems,
  editDisabled,
  editDisabledTitle,
  leading,
  trailing,
}: AppsMenuBarProps) {
  const fileItems: MenuEntry[] = [
    { id: 'new', label: 'New App', disabled: !onNewApp || newAppDisabled, onSelect: () => onNewApp?.() },
    ...(fileExtras?.length ? [{ id: 'sep-extras', kind: 'separator' } as const, ...fileExtras] : []),
  ];

  return (
    <MenuBar label="Apps menus" title="Apps" leading={leading} trailing={trailing} testId="apps-menu-bar" className="flex-wrap">
      <Menu label="File" items={fileItems} testId="apps-menu-file" itemTestIdPrefix="apps-menuitem-" />
      {editItems?.length || editDisabled ? (
        <Menu
          label="Edit"
          items={editItems ?? []}
          disabled={editDisabled}
          title={editDisabled ? editDisabledTitle : undefined}
          testId="apps-menu-edit"
          itemTestIdPrefix="apps-menuitem-"
        />
      ) : null}
    </MenuBar>
  );
}
