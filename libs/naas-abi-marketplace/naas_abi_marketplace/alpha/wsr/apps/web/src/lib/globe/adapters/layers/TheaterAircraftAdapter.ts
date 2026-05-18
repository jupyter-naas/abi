/**
 * TheaterAircraftAdapter
 *
 * Realizes: wv:TheaterAircraftMonitoringProcess
 * ICE consumed: wv:MilitaryAircraftReport[] from /api/mideast-aircraft
 * Sites monitored: wvi:MiddleEastTheater (Iran, Levant, Persian Gulf)
 *
 * Theater aircraft are rendered with a distinct icon (ringed star)
 * and color-coded by civil/military status. This is a separate adapter
 * from MilitaryLayerAdapter because it realizes a different BFO process
 * (TheaterAircraftMonitoringProcess vs global FlightTrackingProcess)
 * and operates within a specific geographic context (the conflict theater).
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';
import type { FlightState } from '@/lib/types';

const THEATER_MIL_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <polygon points="7,1 9,6 13,7 9,8 7,13 5,8 1,7 5,6" fill="#ff4400" opacity="0.95"/>
  <circle cx="7" cy="7" r="2" fill="none" stroke="#ff4400" stroke-width="0.8"/>
</svg>`)}`;

const THEATER_CIV_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">
  <polygon points="5,1 6.5,4 9,5 6.5,6 5,9 3.5,6 1,5 3.5,4" fill="#88aaff" opacity="0.7"/>
</svg>`)}`;

export class TheaterAircraftAdapter extends GlobeLayerBase<FlightState[]> {
  readonly layerId = 'theater-aircraft-layer';
  readonly processType: ProcessType = 'TheaterAircraftMonitoringProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true };

  private _collection: unknown = null;

  async initialize(): Promise<void> {
    const bb = new this.Cesium.BillboardCollection({ scene: this.viewer.scene });
    this.viewer.scene.primitives.add(bb);
    this._collection = bb;
  }

  update(flights: FlightState[]): void {
    const Cesium = this.Cesium;
    const bb = this._collection as { removeAll: () => void; add: (o: unknown) => void; show: boolean } | null;
    if (!bb) return;
    bb.show = true;
    bb.removeAll();
    for (const f of flights) {
      if (f.lat == null || f.lon == null) continue;
      const isMil = f.isMilitary === true;
      bb.add({
        position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, Math.max(f.altitude, 100)),
        image: isMil ? THEATER_MIL_ICON : THEATER_CIV_ICON,
        width: isMil ? 14 : 8, height: isMil ? 14 : 8,
        rotation: -Cesium.Math.toRadians(f.heading),
        alignedAxis: Cesium.Cartesian3.UNIT_Z,
        id: {
          _wv: true, id: f.icao24, name: f.callsign || f.icao24, type: 'flight',
          lat: f.lat, lon: f.lon, altitude: f.altitude,
          velocity: f.velocity, heading: f.heading,
          extra: { isMilitary: isMil ? 1 : 0, theater: 'mideast' },
        },
      });
    }
  }

  setVisible(visible: boolean): void {
    if (this._collection) (this._collection as { show: boolean }).show = visible;
  }

  teardown(): void {
    if (this._collection && this._ctx) {
      try { this._ctx.scene.primitives.remove(this._collection); } catch { /* ok */ }
    }
    this._collection = null;
  }
}
