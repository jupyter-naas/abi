'use client';

import { Menu, MenuBar } from '@/components/ui/menu';
import { useStartNewChat } from '../lib/use-start-new-chat';

/**
 * The Chat section's app menu bar, sitting in the topnav through
 * `Header nav=`. File → New Chat does what the sidebar's New Chat button
 * (and Ctrl+I) does.
 */
export function ChatMenuBar() {
  const startNewChat = useStartNewChat();
  return (
    <MenuBar label="Chat menus" title="Chat" testId="chat-menu-bar">
      <Menu
        label="File"
        testId="chat-menu-file"
        itemTestIdPrefix="chat-menuitem-"
        items={[{ id: 'new-chat', label: 'New Chat', shortcut: 'Ctrl+I', onSelect: startNewChat }]}
      />
    </MenuBar>
  );
}
