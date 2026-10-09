'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';

/**
 * The Search section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as the Ontology bar: a section label, then File.
 * Topics are created in Settings → Search, so "New topic" goes there.
 */
export function SearchMenuBar({ workspaceId, canEdit }: { workspaceId: string; canEdit: boolean }) {
  const router = useRouter();
  const row = APP_MENU_ROW;
  const surface = APP_MENU_SURFACE;
  const trigger = APP_MENU_TRIGGER;

  return <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Search menus" data-testid="search-menu-bar">
    <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Search</span>
    <DropdownMenu.Root><DropdownMenu.Trigger className={trigger}>File <ChevronDown size={11} /></DropdownMenu.Trigger>
      <DropdownMenu.Portal><DropdownMenu.Content align="start" sideOffset={5} className={surface}>
        <DropdownMenu.Item
          className={row}
          disabled={!canEdit}
          title={canEdit ? undefined : 'Only workspace editors can create topics'}
          onSelect={() => router.push(`/workspace/${encodeURIComponent(workspaceId)}/settings/search`)}
        >
          New topic
        </DropdownMenu.Item>
      </DropdownMenu.Content></DropdownMenu.Portal>
    </DropdownMenu.Root>
  </nav>;
}
