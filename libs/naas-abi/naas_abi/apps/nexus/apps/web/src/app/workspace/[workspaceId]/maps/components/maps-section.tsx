'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Layers, LayoutGrid, Map } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { MapsLayerBrandIcon } from './maps-layer-brand-icon';
import { mapsIconMap } from '../lib/maps-icons';
import { groupFeedLayers, groupLayerEntries, type LayoutEntry } from '../lib/layouts';
import { mapsLayerPath, mapsLibraryPath, mapsPath } from '../lib/maps-route';
import { layerPinColor } from '../lib/maps-layer-colors';
import { resolveMapsPinImageUrl } from '../lib/maps-pin-image-url';
import { useMapsLayerParams } from '../lib/use-maps-layer-params';
import { useMapLayers } from '../lib/use-map-layouts';
import { useMapsSidebarLayerCounts } from '../lib/use-maps-sidebar-layer-counts';
import { useMapsStore } from '@/stores/maps';
import './maps-components.css';

export { mapsIconMap } from '../lib/maps-icons';

function LayerSwitch({
  label,
  on,
  onChange,
}: {
  label: string;
  on: boolean;
  onChange: () => void;
}) {
  const title = on
    ? `On the map — click to leave ${label} out`
    : `Not on the map — click to add ${label}`;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`Show ${label} on the map`}
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

/** Swatch in the layer's color with its icon (feed layers). */
function LayerSwatch({ entry }: { entry: LayoutEntry }) {
  const Icon = mapsIconMap[entry.icon] ?? mapsIconMap.MapPin;
  return (
    <span
      className="flex h-[14px] w-[14px] shrink-0 items-center justify-center text-white"
      style={{ background: layerPinColor(entry) }}
      aria-hidden
    >
      {Icon ? <Icon size={10} /> : null}
    </span>
  );
}

function PointCount({ count }: { count: number | undefined }) {
  return count === undefined ? null : (
    <span className="text-[10px] tabular-nums text-muted-foreground" title={`${count} data points`}>
      {count}
    </span>
  );
}

function LayerRow({
  entry,
  workspaceId,
  on,
  active,
  count,
  nested = false,
  onToggle,
  onSelect,
}: {
  entry: LayoutEntry;
  workspaceId: string | null;
  on: boolean;
  active: boolean;
  count?: number;
  nested?: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  return (
    <div className={cn(rowClass(active), nested && 'pl-5')}>
      <Link
        href={mapsLayerPath(workspaceId, entry.id)}
        aria-current={active ? 'page' : undefined}
        title={entry.feedTitle && nested ? `${entry.feedTitle} · ${entry.title}` : entry.description}
        onClick={onSelect}
        className={cn('flex min-w-0 flex-1 items-center gap-2', !on && 'text-muted-foreground')}
      >
        {nested ? <LayerSwatch entry={entry} /> : <MapsLayerBrandIcon entry={entry} size={14} />}
        <span className="flex-1 truncate">{entry.title}</span>
        <PointCount count={count} />
      </Link>
      <LayerSwitch label={entry.title} on={on} onChange={onToggle} />
    </div>
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
  const { entries, error, loading } = useMapLayers();
  useMapsSidebarLayerCounts(workspaceId, entries, loading);
  const layerCounts = useMapsStore((s) => s.layerCounts);
  // Feeds start expanded while one of their layers is on; a click overrides.
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
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

      {groupLayerEntries(entries).map((group) => {
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
            {groupFeedLayers(group.entries).map((item) => {
              if (item.type === 'layer') {
                return (
                  <LayerRow
                    key={item.entry.id}
                    entry={item.entry}
                    count={layerCounts[item.entry.id]}
                    workspaceId={workspaceId}
                    on={isOn(item.entry)}
                    active={layerIds.length === 1 && layerIds[0] === item.entry.id}
                    onToggle={() => setLayerOn(item.entry.id, !isOn(item.entry))}
                    onSelect={() => selectLayerExclusive(item.entry.id)}
                  />
                );
              }
              const ids = item.layers.map((layer) => layer.id);
              const onCount = item.layers.filter(isOn).length;
              const open = expanded[item.feedId] ?? onCount > 0;
              const logo = resolveMapsPinImageUrl(item.logoUrl);
              return (
                <div key={`feed:${item.feedId}`}>
                  <div className={rowClass(false)}>
                    <button
                      type="button"
                      className={cn(
                        'flex min-w-0 flex-1 items-center gap-2 text-left',
                        onCount === 0 && 'text-muted-foreground',
                      )}
                      aria-expanded={open}
                      aria-label={`${item.title}: ${open ? 'hide' : 'show'} its layers`}
                      title={`${item.title}: ${onCount} of ${item.layers.length} layers on`}
                      onClick={() => setExpanded((current) => ({ ...current, [item.feedId]: !open }))}
                    >
                      {logo ? (
                        // eslint-disable-next-line @next/next/no-img-element -- feed logo (API or https)
                        <img src={logo} alt="" width={14} height={14} className="shrink-0" />
                      ) : (
                        <Layers size={14} aria-hidden />
                      )}
                      <span className="min-w-0 truncate">{item.title}</span>
                      {open ? (
                        <ChevronDown size={12} className="shrink-0 text-muted-foreground" aria-hidden />
                      ) : (
                        <ChevronRight size={12} className="shrink-0 text-muted-foreground" aria-hidden />
                      )}
                      <span className="flex-1" />
                      <PointCount count={layerCounts[`feed:${item.feedId}`]} />
                    </button>
                    <LayerSwitch
                      label={`all layers of ${item.title}`}
                      on={onCount === item.layers.length}
                      onChange={() => setLayersOn(ids, onCount !== item.layers.length)}
                    />
                  </div>
                  {open
                    ? item.layers.map((layer) => (
                        <LayerRow
                          key={layer.id}
                          entry={layer}
                          nested
                          count={layerCounts[layer.id]}
                          workspaceId={workspaceId}
                          on={isOn(layer)}
                          active={layerIds.length === 1 && layerIds[0] === layer.id}
                          onToggle={() => setLayerOn(layer.id, !isOn(layer))}
                          onSelect={() => selectLayerExclusive(layer.id)}
                        />
                      ))
                    : null}
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
