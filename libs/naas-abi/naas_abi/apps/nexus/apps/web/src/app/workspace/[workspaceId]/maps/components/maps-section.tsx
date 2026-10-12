'use client';

import { LayoutGrid, Map } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { MapsLayerBrandIcon } from './maps-layer-brand-icon';
import { mapsIconMap } from '../lib/maps-icons';
import { groupLayerEntries, type LayoutEntry } from '../lib/layouts';
import { mapsLayerPath, mapsLibraryPath, mapsPath } from '../lib/maps-route';
import { useMapsLayerParams } from '../lib/use-maps-layer-params';
import { useMapLayers } from '../lib/use-map-layouts';
import './maps-components.css';

export { mapsIconMap } from '../lib/maps-icons';

function LayerSwitch({
  entry,
  on,
  onChange,
}: {
  entry: LayoutEntry;
  on: boolean;
  onChange: () => void;
}) {
  const title = on
    ? `On the map — click to leave ${entry.title} out`
    : `Not on the map — click to add ${entry.title}`;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`Show ${entry.title} on the map`}
      title={title}
      onClick={onChange}
      className={cn(
        'relative h-[14px] w-[25px] flex-shrink-0 rounded-none transition-colors',
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
 * Sidebar: Active layers, then Environment, SIGINT, Situation, and Custom.
 */
export function MapsDatasetGroups({
  dense,
}: {
  dense?: boolean;
}) {
  const { workspaceId, layerIds, isOn, setLayerOn, setLayersOn, selectLayerExclusive } =
    useMapsLayerParams();
  const { entries, error, customLayerGroups } = useMapLayers();
  const combinable = entries.filter((e) => e.combinable);
  const onCount = layerIds.length;
  const allActive = layerIds.length !== 1;

  return (
    <div className={cn('maps-section-list', dense && 'maps-section-list--dense')}>
      {error && <p className="maps-status maps-status--error">{error}</p>}
      <Link
        href={mapsPath(workspaceId, layerIds)}
        aria-current={allActive ? 'page' : undefined}
        className="shell-sidebar-home"
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span>Active layers</span>
        <span className="text-[10px] text-muted-foreground">
          {onCount}/{combinable.length} on
        </span>
      </Link>

      {groupLayerEntries(entries, customLayerGroups).map((group) => {
        const groupCombinable = group.entries.filter((e) => e.combinable);
        const allOn = groupCombinable.length > 0 && groupCombinable.every(isOn);
        return (
          <div key={group.id} className="shell-sidebar-home-gutter mb-2 space-y-0.5">
            <div className="flex items-center justify-between px-2 py-1 text-xs font-medium text-muted-foreground">
              <span>{group.label}</span>
              {groupCombinable.length > 1 && (
                <button
                  type="button"
                  className="text-[10px] hover:text-foreground"
                  onClick={() => setLayersOn(groupCombinable.map((e) => e.id), !allOn)}
                >
                  {allOn ? 'None' : 'All'}
                </button>
              )}
            </div>
            {group.entries.map((entry) => {
              const on = isOn(entry);
              const active = layerIds.length === 1 && layerIds[0] === entry.id;
              return (
                <div key={entry.id} className={rowClass(active)}>
                  <Link
                    href={mapsLayerPath(workspaceId, entry.id)}
                    aria-current={active ? 'page' : undefined}
                    title={entry.description}
                    onClick={() => selectLayerExclusive(entry.id)}
                    className={cn(
                      'flex min-w-0 flex-1 items-center gap-2',
                      !on && 'text-muted-foreground',
                    )}
                  >
                    <MapsLayerBrandIcon entry={entry} size={14} />
                    <span className="flex-1 truncate">{entry.title}</span>
                  </Link>
                  <LayerSwitch entry={entry} on={on} onChange={() => setLayerOn(entry.id, !on)} />
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
      description="Data layers on the map"
      href={getWorkspacePath(currentWorkspaceId, '/maps')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={openLibrary}
    >
      <MapsDatasetGroups dense={isMobilePanel} />
    </CollapsibleSection>
  );
}
