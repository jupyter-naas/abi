'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';
import { mapsSettingsPath } from '../lib/maps-route';

/**
 * The Maps section's app menu bar, sitting in the topnav through
 * `Header nav=`. Layouts are created in Settings → Maps, so New Layout opens
 * it on a blank layout.
 */
export function MapsMenuBar({ workspaceId, canEdit }: { workspaceId: string | null; canEdit: boolean }) {
  const router = useRouter();
  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Maps menus" data-testid="maps-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Maps</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="maps-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            <DropdownMenu.Item
              className={APP_MENU_ROW}
              disabled={!canEdit || !workspaceId}
              title={canEdit ? undefined : 'Only workspace admins can create layouts'}
              onSelect={() => router.push(mapsSettingsPath(workspaceId, { create: true }))}
              data-testid="maps-menuitem-new-layout"
            >
              New Layout
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
