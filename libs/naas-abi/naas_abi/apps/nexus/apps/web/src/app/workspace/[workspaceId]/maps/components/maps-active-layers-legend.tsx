'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, Map as MapIcon } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { MAPS_CATEGORIES } from '../lib/datasets';
import { mapsIconMap } from '../lib/maps-icons';
import { layerPinColor } from '../lib/maps-layer-colors';
import type { LayoutEntry } from '../lib/layouts';
import { mapsLayerPath } from '../lib/maps-route';

export type LayerLegendSublayer = { label: string; count: number };

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
}: {
  entry: LayoutEntry;
  status: LayerLegendStatus | undefined;
  workspaceId: string | null;
  collapsed: boolean;
  onToggle: () => void;
  feedDetail?: ReactNode;
}) {
  const color = layerPinColor(entry);
  const Icon = mapsIconMap[entry.icon] ?? MapIcon;
  const sublayers =
    status && 'count' in status && status.sublayers && status.sublayers.length > 1
      ? status.sublayers
      : undefined;
  const expandable = Boolean(sublayers || feedDetail);

  return (
    <div className="maps-legend__layer">
      <div className="maps-legend__row">
        <span className="maps-layer-marker maps-legend__layer-swatch" style={{ background: color }} aria-hidden>
          <Icon size={11} strokeWidth={2.25} />
        </span>
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
              {sublayers.map((sub) => (
                <li key={sublayerKey(sub.label)} className="maps-legend__sublayer">
                  <span className="maps-legend__sublayer-label">{sub.label}</span>
                  <span className="tabular-nums text-muted-foreground">{sub.count}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {feedDetail ? <div className="maps-legend__layer-detail">{feedDetail}</div> : null}
        </>
      ) : null}
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
  const groups = useMemo(() => {
    return MAPS_CATEGORIES.map(({ id, label }) => ({
      id,
      label,
      entries: entries
        .filter((e) => e.category === id)
        .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)),
    })).filter((g) => g.entries.length > 0);
  }, [entries]);

  const [collapsedLayers, setCollapsedLayers] = useState<Record<string, boolean>>({});

  const toggleLayer = (layerId: string) => {
    setCollapsedLayers((prev) => ({ ...prev, [layerId]: !(prev[layerId] ?? true) }));
  };

  const isLayerCollapsed = (layerId: string) => collapsedLayers[layerId] ?? true;

  return (
    <div className="maps-legend maps-legend--panel" aria-label="Map legend">
      {noLayers ? (
        <p className="maps-legend__hint">None on — use the sidebar switches to add data.</p>
      ) : null}
      {groups.map((group) => (
        <div key={group.id} className="maps-legend__group">
          <div className="maps-legend__group-label">{group.label}</div>
          <div className="maps-legend__group-items">
            {group.entries.map((entry) => (
              <LayerRow
                key={entry.id}
                entry={entry}
                status={statuses[entry.id]}
                workspaceId={workspaceId}
                collapsed={isLayerCollapsed(entry.id)}
                onToggle={() => toggleLayer(entry.id)}
                feedDetail={feedLegendsByLayerId?.[entry.id]}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
