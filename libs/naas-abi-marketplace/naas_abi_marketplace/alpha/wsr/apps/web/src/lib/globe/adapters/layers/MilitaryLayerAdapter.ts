/**
 * MilitaryLayerAdapter
 *
 * Realizes: (global military fleet — subset of FlightTrackingProcess)
 * ICE consumed: wsr:MilitaryAircraftReport[] from /api/military (ADSB.lol → airplanes.live fallback)
 * Material entity rendered: wsr:MilitaryAircraft billboards (orange)
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';
import type { FlightState } from '@/lib/types';

const MIL_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <polygon points="7,1 9,6 13,7 9,8 7,13 5,8 1,7 5,6" fill="#ff8800" opacity="0.95"/>
</svg>`)}`;

export class MilitaryLayerAdapter extends GlobeLayerBase<FlightState[]> {
  readonly layerId = 'military-layer';
  readonly processType: ProcessType = 'FlightTrackingProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true };

  private _collection: unknown = null;
  private _visible = true;
  private _lastFlights: FlightState[] = [];

  async initialize(): Promise<void> {
    const bb = new this.Cesium.BillboardCollection({ scene: this.viewer.scene });
    this.viewer.scene.primitives.add(bb);
    this._collection = bb;
  }

  update(flights: FlightState[]): void {
    this._lastFlights = flights;
    this._render();
  }

  setVisible(visible: boolean): void {
    this._visible = visible;
    if (this._collection) (this._collection as { show: boolean }).show = visible;
    // Re-render with cached data so turning the layer back on is instant
    if (visible) this._render();
  }

  teardown(): void {
    if (this._collection && this._ctx) {
      try { this._ctx.scene.primitives.remove(this._collection); } catch { /* ok */ }
    }
    this._collection = null;
    this._lastFlights = [];
  }

  private _render(): void {
    const Cesium = this.Cesium;
    const bb = this._collection as {
      removeAll: () => void;
      add: (o: unknown) => void;
      show: boolean;
    } | null;
    if (!bb) return;

    bb.show = this._visible;
    if (!this._visible) return;

    bb.removeAll();
    let count = 0;
    for (const f of this._lastFlights) {
      if (f.lat == null || f.lon == null) continue;
      bb.add({
        position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, Math.max(f.altitude, 500)),
        image: MIL_ICON,
        width: 12, height: 12,
        rotation: -Cesium.Math.toRadians(f.heading),
        alignedAxis: Cesium.Cartesian3.UNIT_Z,
        color: Cesium.Color.fromCssColorString('#ff8800').withAlpha(0.9),
        id: {
          _wv: true, id: f.icao24, name: f.callsign, type: 'flight',
          lat: f.lat, lon: f.lon, altitude: f.altitude,
          velocity: f.velocity, heading: f.heading, extra: { isMilitary: 1 },
        },
      });
      count++;
    }
    this.emit({ type: 'data:updated', layerId: this.layerId, payload: { count }, timestamp: Date.now() });
  }
}
