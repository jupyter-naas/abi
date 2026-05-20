/**
 * CityLabelAdapter
 *
 * Realizes: wv:GlobeRenderingProcess (city label sub-process)
 * ICE consumed: static WORLD_CITIES array (wv:UrbanSite instances)
 * Site rendered: wv:UrbanSite labels worldwide
 *
 * Static layer — initialized once, no polling.
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';

export interface CityRecord {
  name: string;
  lat: number;
  lon: number;
}

export class CityLabelAdapter extends GlobeLayerBase<CityRecord[]> {
  readonly layerId = 'city-label-layer';
  readonly processType: ProcessType = 'GlobeRenderingProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true, staticLayer: true };

  private _collection: unknown = null;

  constructor(private readonly cities: CityRecord[]) {
    super();
  }

  async initialize(): Promise<void> {
    const Cesium = this.Cesium;
    const viewer = this.viewer;

    const lbColl = viewer.scene.primitives.add(new Cesium.LabelCollection());
    this._collection = lbColl;

    for (const city of this.cities) {
      lbColl.add({
        position: Cesium.Cartesian3.fromDegrees(city.lon, city.lat, 0),
        text: city.name,
        font: '11px monospace',
        fillColor: Cesium.Color.fromCssColorString('#00ff41').withAlpha(0.85),
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -10),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        translucencyByDistance: new Cesium.NearFarScalar(300000, 1.0, 12000000, 0.0),
        scaleByDistance: new Cesium.NearFarScalar(300000, 1.0, 8000000, 0.3),
      });
    }
  }

  update(cities: CityRecord[]): void {
    // Support dynamic city list updates (e.g., highlight a new city)
    const Cesium = this.Cesium;
    const coll = this._collection as { removeAll: () => void; add: (o: unknown) => void } | null;
    if (!coll) return;
    coll.removeAll();
    for (const city of cities) {
      coll.add({
        position: Cesium.Cartesian3.fromDegrees(city.lon, city.lat, 0),
        text: city.name,
        font: '11px monospace',
        fillColor: Cesium.Color.fromCssColorString('#00ff41').withAlpha(0.85),
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new Cesium.Cartesian2(0, -10),
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        translucencyByDistance: new Cesium.NearFarScalar(300000, 1.0, 12000000, 0.0),
        scaleByDistance: new Cesium.NearFarScalar(300000, 1.0, 8000000, 0.3),
      });
    }
  }

  setVisible(visible: boolean): void {
    if (this._collection) (this._collection as { show: boolean }).show = visible;
  }

  teardown(): void {
    if (this._collection && this._ctx) {
      try { this._ctx.scene.primitives.remove(this._collection); } catch { /* viewer destroyed */ }
    }
    this._collection = null;
  }
}
