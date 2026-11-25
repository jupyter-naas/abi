'use client';

import { Menu, MenuBar } from '@/components/ui/menu';

/** The Tasks app menu bar, sitting in the topnav through `Header nav=`. */
export function TasksMenuBar({ onNewTask, onSettings }: { onNewTask: () => void; onSettings: () => void }) {
  return (
    <MenuBar label="Tasks menus" title="Tasks" testId="tasks-menu-bar">
      <Menu
        label="File"
        testId="tasks-menu-file"
        itemTestIdPrefix="tasks-menuitem-"
        items={[
          { id: 'new-task', label: 'New task', onSelect: onNewTask },
          { id: 'sep', kind: 'separator' },
          { id: 'settings', label: 'Settings…', onSelect: onSettings },
        ]}
      />
    </MenuBar>
  );
}
