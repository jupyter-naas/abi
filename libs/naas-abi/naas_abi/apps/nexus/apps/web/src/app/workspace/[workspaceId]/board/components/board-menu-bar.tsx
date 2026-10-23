'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';

/** The Board's app menu bar, sitting in the topnav through `Header nav=`. */
export function BoardMenuBar({ onNewTask, onSettings }: { onNewTask: () => void; onSettings: () => void }) {
  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Board menus" data-testid="board-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Board</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="board-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item className={APP_MENU_ROW} onSelect={onNewTask} data-testid="board-menuitem-new-task">
              New task
            </DropdownMenu.Item>
            <DropdownMenu.Separator className="my-1 h-px bg-border" />
            <DropdownMenu.Item className={APP_MENU_ROW} onSelect={onSettings} data-testid="board-menuitem-settings">
              Settings…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
