/**
 * BorderLayerAdapter
 *
 * Realizes: wv:GlobeRenderingProcess (country borders sub-process)
 * ICE consumed: Natural Earth 110m GeoJSON (exterior rings only)
 * Site rendered: wv:GeographicSite boundaries worldwide
 *
 * Uses PolylineCollection directly — bypasses GeoJsonDataSource polygon
 * geometry worker (which crashes with RangeError: Too many properties).
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';

const GEOJSON_URL =
  'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson';

export class BorderLayerAdapter extends GlobeLayerBase<void> {
  readonly layerId = 'border-layer';
  readonly processType: ProcessType = 'GlobeRenderingProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true, staticLayer: true };

  private _collection: unknown = null;

  async initialize(): Promise<void> {
    const Cesium = this.Cesium;
    const viewer = this.viewer;

    try {
      const res = await fetch(GEOJSON_URL, { signal: AbortSignal.timeout(15000) });
      if (!res.ok) return;

      const gj = await res.json() as {
        features: Array<{
          geometry: {
            type: 'Polygon' | 'MultiPolygon';
            coordinates: number[][][][] | number[][][];
          } | null;
        }>;
      };

      const mat = Cesium.Material.fromType('Color', {
        color: Cesium.Color.fromCssColorString('#00ff41').withAlpha(0.35),
      });
      const lines = new Cesium.PolylineCollection();

      for (const feat of gj.features) {
        if (!feat.geometry) continue;
        const { type, coordinates } = feat.geometry;
        const rings: number[][][] =
          type === 'Polygon'
            ? [(coordinates as number[][][])[0]]
            : (coordinates as number[][][][]).map((p) => p[0]);

        for (const ring of rings) {
          if (!ring || ring.length < 2) continue;
          lines.add({
            positions: ring.map((c) => Cesium.Cartesian3.fromDegrees(c[0], c[1], 0)),
            width: 1.0,
            material: mat,
          });
        }
      }

      viewer.scene.primitives.add(lines);
      this._collection = lines;
    } catch (err) {
      console.warn('[BorderLayerAdapter] Failed to load borders:', err);
    }
  }

  update(): void { /* static layer — no runtime updates */ }

  setVisible(visible: boolean): void {
    if (this._collection) (this._collection as { show: boolean }).show = visible;
  }

  teardown(): void {
    if (this._collection && this._ctx) {
      try {
        this._ctx.scene.primitives.remove(this._collection);
      } catch { /* viewer already destroyed */ }
    }
    this._collection = null;
  }
}
