/**
 * EarthquakeLayerAdapter
 *
 * Realizes: wv:EarthquakeMonitoringProcess
 * ICE consumed: wv:EarthquakeEventRecord[] from /api/earthquakes (USGS)
 * Quality rendered: wv:EarthquakeMagnitude → ellipse radius scaling
 *
 * Color → magnitude thresholds encode the wv:ThreatSeverityLevel quality:
 *   mag ≥ 6 → critical (#ff2200)
 *   mag ≥ 4 → high    (#ff6600)
 *   mag < 4 → medium  (#ffaa00)
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';
import type { EarthquakeFeature } from '@/lib/types';

export class EarthquakeLayerAdapter extends GlobeLayerBase<EarthquakeFeature[]> {
  readonly layerId = 'earthquake-layer';
  readonly processType: ProcessType = 'EarthquakeMonitoringProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true };

  private _entities: unknown[] = [];

  async initialize(): Promise<void> { /* entities added dynamically */ }

  update(quakes: EarthquakeFeature[]): void {
    if (!quakes) return;
    const Cesium = this.Cesium;
    const viewer = this.viewer as {
      entities: { add: (e: unknown) => unknown; remove: (e: unknown) => void };
      isDestroyed?: () => boolean;
    };
    if (!viewer || viewer.isDestroyed?.()) return;

    this._entities.forEach((e) => { try { viewer.entities.remove(e); } catch { /* ok */ } });
    this._entities = [];

    for (const q of (quakes ?? [])) {
      if (q.lat == null || q.lon == null || isNaN(q.lat) || isNaN(q.lon)) continue;
      const radius = Math.max(30000, q.mag * 60000);
      const color = q.mag >= 6 ? '#ff2200' : q.mag >= 4 ? '#ff6600' : '#ffaa00';
      // Cesium's entity `id` is used as an AssociativeArray key and MUST be a
      // plain string. Earthquake ellipses are display-only zone overlays; they
      // don't need the _wsr click payload (no track / fly-to behaviour).
      const ent = viewer.entities.add({
        id: `eq-${q.id}`,
        position: Cesium.Cartesian3.fromDegrees(q.lon, q.lat, 0),
        ellipse: {
          semiMinorAxis: radius,
          semiMajorAxis: radius,
          height: 0,
          material: Cesium.Color.fromCssColorString(color).withAlpha(0.3),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(color).withAlpha(0.8),
        },
      });
      this._entities.push(ent);
    }
    this.emit({ type: 'data:updated', layerId: this.layerId, payload: { count: quakes.length }, timestamp: Date.now() });
  }

  setVisible(visible: boolean): void {
    for (const e of this._entities) (e as { show: boolean }).show = visible;
  }

  teardown(): void {
    const viewer = this._ctx?.viewer as { entities: { remove: (e: unknown) => void } } | null;
    if (viewer) this._entities.forEach((e) => { try { viewer.entities.remove(e); } catch { /* ok */ } });
    this._entities = [];
  }
}
