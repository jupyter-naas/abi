'use client';

import { useRouter } from 'next/navigation';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';
import { mapsDeploymentRestrictsLayerCatalog } from '@/app/workspace/[workspaceId]/maps/lib/maps-deployment';
import { mapsSettingsPath } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';

/**
 * The Maps section's app menu bar, sitting in the topnav through
 * `Header nav=`. File → New layer / GeoJSON layers modals; Settings → Maps.
 */
export function MapsMenuBar({
  workspaceId,
  onNewLayer,
  onNewBasemap,
  onGeoJsonLayers,
}: {
  workspaceId: string | null;
  onNewLayer: () => void;
  onNewBasemap: () => void;
  onGeoJsonLayers: () => void;
}) {
  const router = useRouter();
  const needsWorkspace = { disabled: !workspaceId, title: workspaceId ? undefined : 'Open Maps inside a workspace' };
  const items: MenuEntry[] = [
    ...(mapsDeploymentRestrictsLayerCatalog()
      ? []
      : ([
          { id: 'new-layer', label: 'New layer', ...needsWorkspace, keepOpen: true, onSelect: onNewLayer },
          { id: 'new-basemap', label: 'New basemap', ...needsWorkspace, keepOpen: true, onSelect: onNewBasemap },
          { id: 'geojson-layers', label: 'GeoJSON layers', keepOpen: true, onSelect: onGeoJsonLayers },
          { id: 'sep-settings', kind: 'separator' },
        ] satisfies MenuEntry[])),
    { id: 'settings', label: 'Settings', ...needsWorkspace, onSelect: () => workspaceId && router.push(mapsSettingsPath(workspaceId)) },
  ];

  return (
    <MenuBar label="Maps menus" title="Maps" testId="maps-menu-bar">
      <Menu label="File" testId="maps-menu-file" itemTestIdPrefix="maps-menuitem-" items={items} />
    </MenuBar>
  );
}
