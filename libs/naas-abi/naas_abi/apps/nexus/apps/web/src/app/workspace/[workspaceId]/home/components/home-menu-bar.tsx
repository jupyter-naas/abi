'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';
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
  const fileItems = fileMenuRows.filter((row) => row.kind === 'item');

  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Home menus" data-testid="home-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Home</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="home-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            {fileItems.length === 0 ? (
              <DropdownMenu.Item className={APP_MENU_ROW} disabled>
                No items
              </DropdownMenu.Item>
            ) : (
              fileMenuRows.map((row) =>
                row.kind === 'separator' ? (
                  <DropdownMenu.Separator key={row.id} className="my-1 h-px bg-border" />
                ) : (
                  <DropdownMenu.Item
                    key={row.id}
                    className={APP_MENU_ROW}
                    onSelect={row.navigate}
                    data-href={row.href}
                  >
                    {row.label}
                  </DropdownMenu.Item>
                ),
              )
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="home-menu-edit">
          Edit <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item
              className={APP_MENU_ROW}
              disabled={!canEditBackground}
              title={
                canEditBackground ? undefined : 'Only workspace admins can change the desktop wallpaper'
              }
              onSelect={onEditBackground}
              data-testid="home-menuitem-desktop-wallpaper"
            >
              Desktop wallpaper…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
