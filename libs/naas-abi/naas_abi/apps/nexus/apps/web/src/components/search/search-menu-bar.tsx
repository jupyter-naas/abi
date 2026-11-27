'use client';

import { useRouter } from 'next/navigation';
import { Menu, MenuBar } from '@/components/ui/menu';

/**
 * The Search section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as the Ontology bar: a section label, then File.
 * Topics are created in Settings → Search, so "New topic" goes there.
 */
export function SearchMenuBar({ workspaceId, canEdit }: { workspaceId: string; canEdit: boolean }) {
  const router = useRouter();
  return (
    <MenuBar label="Search menus" title="Search" testId="search-menu-bar">
      <Menu
        label="File"
        items={[{
          id: 'new-topic',
          label: 'New topic',
          disabled: !canEdit,
          title: canEdit ? undefined : 'Only workspace editors can create topics',
          onSelect: () => router.push(`/workspace/${encodeURIComponent(workspaceId)}/settings/search`),
        }]}
      />
    </MenuBar>
  );
}
