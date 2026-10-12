'use client';

import { useCallback, useEffect, useState } from 'react';
import { X } from 'lucide-react';
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

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const layerIds = Object.keys(store).sort();

  return (
    <div className="maps-geojson-modal" role="dialog" aria-modal="true" aria-labelledby="maps-geojson-modal-title">
      <button
        type="button"
        className="maps-geojson-modal__backdrop"
        aria-label="Close layer GeoJSON dialog"
        onClick={onClose}
      />
      <div className="maps-geojson-modal__card">
        <header className="maps-geojson-modal__header">
          <div className="min-w-0">
            <h2 id="maps-geojson-modal-title" className="maps-geojson-modal__title">
              Layer GeoJSON (local)
            </h2>
            <p className="maps-geojson-modal__hint">
              Last fetch per layer in <code>localStorage</code> key{' '}
              <code>nexus-maps-layer-geojson-debug</code>.
            </p>
          </div>
          <button
            type="button"
            className="maps-geojson-modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            <X size={18} aria-hidden />
          </button>
        </header>

        <div className="maps-geojson-modal__body">
          {!layerIds.length ? (
            <p className="maps-geojson-modal__empty">
              Waiting for layer feeds… Snapshots save after each successful load.
            </p>
          ) : (
            <ul className="maps-geojson-debug__list maps-geojson-modal__list">
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
        </div>

        <footer className="maps-geojson-modal__footer">
          <button
            type="button"
            className="maps-geojson-debug__btn maps-geojson-debug__btn--footer"
            disabled={!layerIds.length}
            onClick={() => downloadJson('maps-layers.geojson.json', store)}
          >
            Download all
          </button>
          <button
            type="button"
            className="maps-geojson-debug__btn maps-geojson-debug__btn--footer"
            onClick={() => clearLayerGeoJsonDebug()}
          >
            Clear
          </button>
        </footer>
      </div>
    </div>
  );
}
