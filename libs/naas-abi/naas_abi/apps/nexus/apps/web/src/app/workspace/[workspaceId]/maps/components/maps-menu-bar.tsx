'use client';

import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { APP_MENU_ROW, APP_MENU_SURFACE, APP_MENU_TRIGGER } from '@/components/shell/app-menu-classes';
import { mapsDeploymentRestrictsLayerCatalog } from '@/app/workspace/[workspaceId]/maps/lib/maps-deployment';
import { mapsSettingsPath } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * The Maps section's app menu bar, sitting in the topnav through
 * `Header nav=`. File → New layer / GeoJSON layers modals; Settings → Maps.
 */
export function MapsMenuBar({
  workspaceId,
  onNewLayer,
  onGeoJsonLayers,
}: {
  workspaceId: string | null;
  onNewLayer: () => void;
  onGeoJsonLayers: () => void;
}) {
  const router = useRouter();
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const catalogRestricted = mapsDeploymentRestrictsLayerCatalog();

  return (
    <nav className="flex min-w-0 shrink-0 items-center gap-1" aria-label="Maps menus" data-testid="maps-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Maps</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger className={APP_MENU_TRIGGER} data-testid="maps-menu-file">
          File <ChevronDown size={11} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="start" sideOffset={5} className={APP_MENU_SURFACE}>
            {!catalogRestricted ? (
              <>
                <DropdownMenu.Item
                  className={APP_MENU_ROW}
                  disabled={!workspaceId}
                  title={workspaceId ? undefined : 'Open Maps inside a workspace'}
                  onSelect={(event) => {
                    event.preventDefault();
                    onNewLayer();
                  }}
                  data-testid="maps-menuitem-new-layer"
                >
                  New layer
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  className={APP_MENU_ROW}
                  onSelect={(event) => {
                    event.preventDefault();
                    onGeoJsonLayers();
                  }}
                  data-testid="maps-menuitem-geojson-layers"
                >
                  GeoJSON layers
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
              </>
            ) : null}
            <DropdownMenu.Item
              className={APP_MENU_ROW}
              disabled={!workspaceId}
              title={workspaceId ? undefined : 'Open Maps inside a workspace'}
              onSelect={() => {
                if (!workspaceId) return;
                setActivePanelSection('settings');
                router.push(mapsSettingsPath(workspaceId));
              }}
              data-testid="maps-menuitem-settings"
            >
              Settings
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </nav>
  );
}
