'use client';

import {
  Activity,
  Building2,
  AlertTriangle,
  Bell,
  Brain,
  CloudLightning,
  Crosshair,
  Flame,
  Globe,
  Laptop,
  Layers,
  LayoutGrid,
  Map,
  MapPin,
  Mountain,
  Newspaper,
  Plane,
  Rocket,
  Satellite,
  Ship,
  Sparkles,
  Thermometer,
  Wind,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useMapsStore } from '@/stores/maps';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { ALL_LAYOUTS_ID, groupLayoutEntries, type LayoutEntry } from '../lib/layouts';
import { mapsAllLayoutsPath, mapsDatasetPath, mapsLibraryPath, parseMapsRoute } from '../lib/maps-route';
import { useMapLayouts } from '../lib/use-map-layouts';
import './maps-components.css';

export const mapsIconMap: Record<string, LucideIcon> = {
  Activity,
  Building2,
  AlertTriangle,
  Bell,
  Brain,
  CloudLightning,
  Crosshair,
  Flame,
  Globe,
  Laptop,
  Layers,
  LayoutGrid,
  Map,
  MapPin,
  Mountain,
  Newspaper,
  Plane,
  Rocket,
  Satellite,
  Ship,
  Sparkles,
  Thermometer,
  Wind,
};

/** Same square switch as the Search sidebar. */
function LayoutSwitch({
  entry,
  on,
  onChange,
  exclusive,
}: {
  entry: LayoutEntry;
  on: boolean;
  onChange: () => void;
  /** Basemap: one choice, not a stackable layout. */
  exclusive?: boolean;
}) {
  const title = exclusive
    ? on
      ? `${entry.title} is the basemap`
      : `Use ${entry.title} as the basemap`
    : on
      ? `On the map — click to leave ${entry.title} out`
      : `Not on the map — click to add ${entry.title}`;
  return (
    <button
      type="button"
      role={exclusive ? 'radio' : 'switch'}
      aria-checked={on}
      aria-label={exclusive ? `Use ${entry.title} as the basemap` : `Show ${entry.title} on the map`}
      title={title}
      onClick={onChange}
      className={cn(
        'relative h-[14px] w-[25px] flex-shrink-0 rounded-none transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        on ? 'bg-workspace-accent' : 'bg-muted-foreground/30',
      )}
    >
      <span
        className={cn(
          'absolute top-[2px] h-[10px] w-[10px] rounded-none bg-white shadow transition-all',
          on ? 'left-[13px]' : 'left-[2px]',
        )}
      />
    </button>
  );
}

function rowClass(active: boolean) {
  return cn(
    'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left search-sidebar-list-row transition-colors hover:bg-workspace-accent-10',
    active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-foreground',
  );
}

/**
 * The layout list: All layouts first, then Basemap (pick one), then Public and
 * Custom. Each row opens that layer alone. A basemap radio changes the
 * background; a layout switch stacks that data on it. Hidden layouts
 * (Settings → Maps) are left out.
 */
export function MapsDatasetGroups({
  dense,
}: {
  /** Larger touch targets for mobile panel / library list. */
  dense?: boolean;
}) {
  const pathname = usePathname();
  const { workspaceId, entries, isOn, error, basemapId } = useMapLayouts();
  const setLayoutOn = useMapsStore((s) => s.setLayoutOn);
  const setLayoutsOn = useMapsStore((s) => s.setLayoutsOn);
  const setBasemap = useMapsStore((s) => s.setBasemap);
  const { datasetId } = parseMapsRoute(pathname);
  const combinable = entries.filter((e) => e.combinable);
  const onCount = combinable.filter(isOn).length;
  const allActive = datasetId === ALL_LAYOUTS_ID;

  return (
    <div className={cn('maps-section-list', dense && 'maps-section-list--dense')}>
      {error && <p className="maps-status maps-status--error">{error}</p>}
      <Link
        href={mapsAllLayoutsPath(workspaceId)}
        aria-current={allActive ? 'page' : undefined}
        className="shell-sidebar-home"
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span>All layouts</span>
        <span className="text-[10px] text-muted-foreground">
          {onCount}/{combinable.length} on
        </span>
      </Link>

      {groupLayoutEntries(entries).map((group) => {
        const basemapGroup = group.id === 'basemap';
        const groupCombinable = group.entries.filter((e) => e.combinable);
        const allOn = groupCombinable.length > 0 && groupCombinable.every(isOn);
        return (
          <div
            key={group.id}
            className="shell-sidebar-home-gutter mb-2 space-y-0.5"
            role={basemapGroup ? 'radiogroup' : undefined}
            aria-label={basemapGroup ? 'Basemap' : undefined}
          >
            <div className="flex items-center justify-between px-2 py-1 text-xs font-medium text-muted-foreground">
              <span>{group.label}</span>
              {groupCombinable.length > 1 && (
                <button
                  type="button"
                  className="text-[10px] hover:text-foreground"
                  onClick={() => setLayoutsOn(groupCombinable.map((e) => e.id), !allOn)}
                >
                  {allOn ? 'None' : 'All'}
                </button>
              )}
            </div>
            {group.entries.map((entry) => {
              const IconComponent = mapsIconMap[entry.icon] || Map;
              const on = basemapGroup ? entry.id === basemapId : isOn(entry);
              const active = datasetId === entry.id;
              return (
                <div key={entry.id} className={rowClass(active)}>
                  <Link
                    href={mapsDatasetPath(workspaceId, entry.id)}
                    aria-current={active ? 'page' : undefined}
                    title={entry.description}
                    className={cn(
                      'flex min-w-0 flex-1 items-center gap-2',
                      !on && 'text-muted-foreground',
                    )}
                  >
                    <IconComponent size={14} className="flex-shrink-0" />
                    <span className="flex-1 truncate">{entry.title}</span>
                  </Link>
                  <LayoutSwitch
                    entry={entry}
                    on={on}
                    exclusive={basemapGroup}
                    onChange={() => (basemapGroup ? setBasemap(entry.id) : setLayoutOn(entry.id, !on))}
                  />
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

export function MapsSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  const openLibrary = () => {
    router.push(mapsLibraryPath(currentWorkspaceId));
  };

  return (
    <CollapsibleSection
      id="maps"
      icon={<Map size={18} />}
      label="Maps"
      description="Basemap and map layouts"
      href={getWorkspacePath(currentWorkspaceId, '/maps')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={openLibrary}
    >
      <MapsDatasetGroups dense={isMobilePanel} />
    </CollapsibleSection>
  );
}
