'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import {
  clearLayerGeoJsonDebug,
  downloadJson,
  loadLayerGeoJsonDebugStore,
  type LayerGeoJsonDebugStore,
} from '../lib/maps-layer-geojson-debug';

export function MapsLayerGeoJsonDebugPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [store, setStore] = useState<LayerGeoJsonDebugStore>({});
  const [openLayer, setOpenLayer] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setStore(loadLayerGeoJsonDebugStore());
  }, []);

  useEffect(() => {
    if (!open) return;
    refresh();
    const onUpdate = () => refresh();
    window.addEventListener('nexus-maps-geojson-debug-updated', onUpdate);
    return () => window.removeEventListener('nexus-maps-geojson-debug-updated', onUpdate);
  }, [open, refresh]);

  if (!open) return null;

  const layerIds = Object.keys(store).sort();

  return (
    <Dialog
      size="lg"
      title="GeoJSON layers"
      description={
        <>
          Last fetch per active layer, stored in this browser (<code>nexus-maps-layer-geojson-debug</code>).
        </>
      }
      onClose={onClose}
      footer={
        <>
          <Button
            variant="secondary"
            size="sm"
            disabled={!layerIds.length}
            onClick={() => downloadJson('maps-layers.geojson.json', store)}
          >
            Download all
          </Button>
          <Button variant="secondary" size="sm" onClick={() => clearLayerGeoJsonDebug()}>
            Clear
          </Button>
        </>
      }
    >
      {!layerIds.length ? (
        <p className="text-muted-foreground">Waiting for layer feeds… Snapshots save after each successful load.</p>
      ) : (
        <ul className="maps-geojson-debug__list border border-border/55 bg-muted/10 px-3 py-2">
          {layerIds.map((layerId) => {
            const row = store[layerId];
            const count = row.collection.features.length;
            const title = row.collection.nexus?.layerTitle ?? layerId;
            const expanded = openLayer === layerId;
            return (
              <li key={layerId} className="maps-geojson-debug__item">
                <div className="maps-geojson-debug__row">
                  <button
                    type="button"
                    className="maps-geojson-debug__layer-toggle"
                    aria-expanded={expanded}
                    onClick={() => setOpenLayer(expanded ? null : layerId)}
                  >
                    <span className="truncate">{title}</span>
                    <span className="tabular-nums text-muted-foreground">{count}</span>
                  </button>
                  <button
                    type="button"
                    className="maps-geojson-debug__btn"
                    onClick={() => downloadJson(`${layerId}.geojson`, row.collection)}
                  >
                    .geojson
                  </button>
                </div>
                {expanded ? (
                  <pre className="maps-geojson-debug__preview">{JSON.stringify(row.collection, null, 2)}</pre>
                ) : null}
                <div className="maps-geojson-debug__meta">
                  saved {row.savedAt}
                  {row.collection.nexus?.fetchedAt ? ` · fetched ${row.collection.nexus.fetchedAt}` : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Dialog>
  );
}
