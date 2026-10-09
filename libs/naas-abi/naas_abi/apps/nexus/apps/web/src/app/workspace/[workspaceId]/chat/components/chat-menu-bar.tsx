'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';
import { useStartNewChat } from '../lib/use-start-new-chat';

/**
 * The Chat section's app menu bar, sitting in the topnav through
 * `Header nav=`. File → New Chat does what the sidebar's New Chat button
 * (and Ctrl+I) does.
 */
export function ChatMenuBar() {
  const startNewChat = useStartNewChat();

  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Chat menus" data-testid="chat-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Chat</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="chat-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item className={APP_MENU_ROW} onSelect={startNewChat} data-testid="chat-menuitem-new-chat">
              New Chat
              <span className="ml-auto pl-4 text-[10px] text-muted-foreground">Ctrl+I</span>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
