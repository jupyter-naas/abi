'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';

/**
 * The Home section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as the other sections: a label, then File.
 */
export function HomeMenuBar({
  canEditBackground,
  onEditBackground,
}: {
  /** Workspace owners and admins only; others see the item greyed. */
  canEditBackground: boolean;
  onEditBackground: () => void;
}) {
  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Home menus" data-testid="home-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Home</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="home-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item
              className={APP_MENU_ROW}
              disabled={!canEditBackground}
              title={canEditBackground ? undefined : 'Only workspace admins can change the background image'}
              onSelect={onEditBackground}
              data-testid="home-menuitem-edit-background"
            >
              Edit background image…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
