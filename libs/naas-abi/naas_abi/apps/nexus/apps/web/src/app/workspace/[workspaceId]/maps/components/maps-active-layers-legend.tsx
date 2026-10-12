'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, Map as MapIcon } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { groupFeedLayers, groupLayerEntries } from '../lib/layouts';
import { useMapLayers } from '../lib/use-map-layouts';
import { MapsLayerBrandIcon } from './maps-layer-brand-icon';
import { resolveMapsPinImageUrl } from '../lib/maps-pin-image-url';
import { mapsIconMap } from '../lib/maps-icons';
import { layerPinColor } from '../lib/maps-layer-colors';
import type { LayoutEntry } from '../lib/layouts';
import { mapsLayerPath } from '../lib/maps-route';

export type LayerLegendSublayer = {
  label: string;
  count: number;
  color?: string;
  icon?: string;
};

export type LayerLegendStatus =
  | { count: number; sublayers?: LayerLegendSublayer[] }
  | { error: string };

export interface MapsActiveLayersLegendProps {
  workspaceId: string | null;
  entries: LayoutEntry[];
  statuses: Record<string, LayerLegendStatus>;
  noLayers: boolean;
  /** Symbology rows per layer id (expand under each layer row). */
  feedLegendsByLayerId?: Record<string, ReactNode>;
}

function sublayerKey(label: string): string {
  return label.toLowerCase().replace(/\s+/g, '-');
}

function LayerRow({
  entry,
  status,
  workspaceId,
  collapsed,
  onToggle,
  feedDetail,
  inFeed = false,
}: {
  entry: LayoutEntry;
  status: LayerLegendStatus | undefined;
  workspaceId: string | null;
  collapsed: boolean;
  onToggle: () => void;
  feedDetail?: ReactNode;
  /** Listed under its feed row: its own color and icon, not the feed logo. */
  inFeed?: boolean;
}) {
  const color = layerPinColor(entry);
  const logoUrl = inFeed ? undefined : resolveMapsPinImageUrl(entry.layerLogoUrl);
  const Icon = mapsIconMap[entry.icon] ?? MapIcon;
  const sublayers =
    status && 'count' in status && status.sublayers && status.sublayers.length > 1
      ? status.sublayers
      : undefined;
  const expandable = Boolean(sublayers || feedDetail);

  return (
    <div className={cn('maps-legend__layer', inFeed && 'maps-legend__layer--in-feed')}>
      <div className="maps-legend__row">
        {logoUrl ? (
          <span className="maps-layer-marker maps-layer-marker--logo maps-legend__layer-swatch" aria-hidden>
            <img src={logoUrl} alt="" className="maps-layer-marker__logo" />
          </span>
        ) : (
          <span className="maps-layer-marker maps-legend__layer-swatch" style={{ background: color }} aria-hidden>
            <Icon size={11} strokeWidth={2.25} />
          </span>
        )}
        {expandable ? (
          <button
            type="button"
            className="maps-legend__layer-title maps-legend__layer-title--expandable"
            aria-expanded={!collapsed}
            onClick={onToggle}
          >
            <span className="min-w-0 truncate text-left">{entry.title}</span>
            <ChevronDown
              size={12}
              className={cn('maps-legend__chevron', collapsed && 'maps-legend__chevron--collapsed')}
              aria-hidden
            />
          </button>
        ) : (
          <Link href={mapsLayerPath(workspaceId, entry.id)} className="maps-legend__layer-title hover:underline">
            {entry.title}
          </Link>
        )}
        <span
          className="tabular-nums text-muted-foreground"
          title={status && 'error' in status ? status.error : undefined}
        >
          {!status ? '…' : 'error' in status ? 'error' : status.count}
        </span>
      </div>
      {!collapsed ? (
        <>
          {sublayers ? (
            <ul className="maps-legend__sublayers">
              {sublayers.map((sub) => {
                const SubIcon = mapsIconMap[sub.icon ?? ''] ?? MapIcon;
                const swatchColor = sub.color ?? color;
                return (
                  <li key={sublayerKey(sub.label)} className="maps-legend__sublayer">
                    <span className="maps-legend__sublayer-leading">
                      <span
                        className="maps-layer-marker maps-legend__layer-swatch maps-legend__sublayer-swatch"
                        style={{ background: swatchColor }}
                        aria-hidden
                      >
                        <SubIcon size={10} strokeWidth={2.25} />
                      </span>
                      <span className="maps-legend__sublayer-label">{sub.label}</span>
                    </span>
                    <span className="tabular-nums text-muted-foreground">{sub.count}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {feedDetail ? <div className="maps-legend__layer-detail">{feedDetail}</div> : null}
        </>
      ) : null}
    </div>
  );
}

/** A layer feed with its active layers, collapsible like the sidebar. */
function FeedRow({
  title,
  logoUrl,
  layers,
  statuses,
  workspaceId,
  collapsed,
  onToggle,
  isLayerCollapsed,
  onToggleLayer,
  feedLegendsByLayerId,
}: {
  title: string;
  logoUrl?: string;
  layers: LayoutEntry[];
  statuses: Record<string, LayerLegendStatus>;
  workspaceId: string | null;
  collapsed: boolean;
  onToggle: () => void;
  isLayerCollapsed: (layerId: string) => boolean;
  onToggleLayer: (layerId: string) => void;
  feedLegendsByLayerId?: Record<string, ReactNode>;
}) {
  const logo = resolveMapsPinImageUrl(logoUrl);
  const counts = layers.map((layer) => statuses[layer.id]);
  const loading = counts.some((status) => !status);
  const total = counts.reduce((sum, status) => sum + (status && 'count' in status ? status.count : 0), 0);
  return (
    <div className="maps-legend__layer maps-legend__feed">
      <div className="maps-legend__row">
        {logo ? (
          <span className="maps-layer-marker maps-layer-marker--logo maps-legend__layer-swatch" aria-hidden>
            <img src={logo} alt="" className="maps-layer-marker__logo" />
          </span>
        ) : (
          <span className="maps-layer-marker maps-legend__layer-swatch" style={{ background: layerPinColor(layers[0]!) }} aria-hidden>
            <MapIcon size={11} strokeWidth={2.25} />
          </span>
        )}
        <button
          type="button"
          className="maps-legend__layer-title maps-legend__layer-title--expandable"
          aria-expanded={!collapsed}
          onClick={onToggle}
          title={`${title}: ${layers.length} layer${layers.length === 1 ? '' : 's'} on`}
        >
          <span className="min-w-0 truncate text-left">{title}</span>
          <ChevronDown
            size={12}
            className={cn('maps-legend__chevron', collapsed && 'maps-legend__chevron--collapsed')}
            aria-hidden
          />
        </button>
        <span className="tabular-nums text-muted-foreground">{loading ? '…' : total}</span>
      </div>
      {!collapsed
        ? layers.map((layer) => (
            <LayerRow
              key={layer.id}
              entry={layer}
              inFeed
              status={statuses[layer.id]}
              workspaceId={workspaceId}
              collapsed={isLayerCollapsed(layer.id)}
              onToggle={() => onToggleLayer(layer.id)}
              feedDetail={feedLegendsByLayerId?.[layer.id]}
            />
          ))
        : null}
    </div>
  );
}

export function MapsActiveLayersLegend({
  workspaceId,
  entries,
  statuses,
  noLayers,
  feedLegendsByLayerId,
}: MapsActiveLayersLegendProps) {
  const { customLayerGroups } = useMapLayers();
  const groups = useMemo(
    () => groupLayerEntries(entries, customLayerGroups),
    [entries, customLayerGroups],
  );

  const [collapsedLayers, setCollapsedLayers] = useState<Record<string, boolean>>({});

  const toggleLayer = (layerId: string) => {
    setCollapsedLayers((prev) => ({ ...prev, [layerId]: !(prev[layerId] ?? true) }));
  };

  const isLayerCollapsed = (layerId: string) => collapsedLayers[layerId] ?? true;
  // Feeds start open (their layers are what is on the map).
  const [collapsedFeeds, setCollapsedFeeds] = useState<Record<string, boolean>>({});

  return (
    <div className="maps-legend maps-legend--panel" aria-label="Map legend">
      {noLayers ? (
        <p className="maps-legend__hint">None on — use the sidebar switches to add data.</p>
      ) : null}
      {groups.map((group) => (
        <div key={group.id} className="maps-legend__group">
          <div className="maps-legend__group-label">{group.label}</div>
          <div className="maps-legend__group-items">
            {groupFeedLayers(group.entries).map((item) =>
              item.type === 'feed' ? (
                <FeedRow
                  key={`feed:${item.feedId}`}
                  title={item.title}
                  logoUrl={item.logoUrl}
                  layers={item.layers}
                  statuses={statuses}
                  workspaceId={workspaceId}
                  collapsed={collapsedFeeds[item.feedId] ?? false}
                  onToggle={() =>
                    setCollapsedFeeds((prev) => ({ ...prev, [item.feedId]: !(prev[item.feedId] ?? false) }))
                  }
                  isLayerCollapsed={isLayerCollapsed}
                  onToggleLayer={toggleLayer}
                  feedLegendsByLayerId={feedLegendsByLayerId}
                />
              ) : (
                <LayerRow
                  key={item.entry.id}
                  entry={item.entry}
                  status={statuses[item.entry.id]}
                  workspaceId={workspaceId}
                  collapsed={isLayerCollapsed(item.entry.id)}
                  onToggle={() => toggleLayer(item.entry.id)}
                  feedDetail={feedLegendsByLayerId?.[item.entry.id]}
                />
              ),
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
