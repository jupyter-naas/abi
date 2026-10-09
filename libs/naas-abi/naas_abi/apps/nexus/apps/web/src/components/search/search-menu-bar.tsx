'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { useRouter } from 'next/navigation';

/**
 * The Search section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as the Ontology bar: a section label, then File.
 * Topics are created in Settings → Search, so "New topic" goes there.
 */
export function SearchMenuBar({ workspaceId, canEdit }: { workspaceId: string; canEdit: boolean }) {
  const router = useRouter();
  const row = 'flex cursor-default select-none items-center gap-2 px-3 py-1.5 text-xs outline-none ![border-radius:0] data-[highlighted]:bg-transparent data-[disabled]:opacity-50';
  const surface = 'z-[300] min-w-[190px] border-0 bg-card p-1 text-foreground !shadow-none outline-none !ring-0 focus:!ring-0 focus-visible:!ring-0 ![border-radius:0]';
  const trigger = 'flex items-center gap-1 border-0 bg-transparent px-2 py-1 text-xs shadow-none outline-none ring-0 ![border-radius:0] hover:bg-transparent focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0 active:bg-transparent data-[state=open]:bg-transparent data-[state=open]:shadow-none';

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
