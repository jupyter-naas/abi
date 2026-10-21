/**
 * CCTVLayerAdapter
 *
 * Realizes: wv:CCTVStreamingProcess
 * ICE consumed: wv:OntologyCCTVCameraUnit[] from /api/cctv
 * Material entity rendered: wv:CCTVCameraUnit positioned at wv:GeographicSite
 *
 * Visibility is altitude-gated: cameras only show when camera height < 20Mm.
 * This is a wv:CacheDuration quality: cameras are hidden above regional zoom.
 *
 * Click events emit 'cctv:open' to the GlobeEngine event bus, which
 * WSR.tsx subscribes to in order to open the CCTVPanel.
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';
import type { CCTVCamera } from '@/lib/types';

const CCTV_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">
  <rect x="1" y="5" width="11" height="8" rx="1" fill="none" stroke="#ff3366" stroke-width="1.5"/>
  <polygon points="12,7 17,5 17,13 12,11" fill="#ff3366" opacity="0.85"/>
  <circle cx="5" cy="9" r="1.5" fill="#ff3366"/>
  <line x1="1" y1="2" x2="3" y2="5" stroke="#ff3366" stroke-width="1.2"/>
</svg>`)}`;

export class CCTVLayerAdapter extends GlobeLayerBase<CCTVCamera[]> {
  readonly layerId = 'cctv-layer';
  readonly processType: ProcessType = 'CCTVStreamingProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true };

  private _collection: unknown = null;
  private _cameras: CCTVCamera[] = [];
  private _visible = true;

  /** Provided by WSR via setAltitudeRef() — determines icon size */
  private _getAltitude: () => number = () => 20000000;

  setAltitudeRef(fn: () => number): void {
    this._getAltitude = fn;
  }

  async initialize(): Promise<void> {
    const Cesium = this.Cesium;
    const viewer = this.viewer;
    const bb = new Cesium.BillboardCollection({ scene: viewer.scene });
    viewer.scene.primitives.add(bb);
    this._collection = bb;
  }

  update(cameras: CCTVCamera[]): void {
    this._cameras = cameras;
    this._render();
    this.emit({ type: 'data:updated', layerId: this.layerId, payload: { count: cameras.length }, timestamp: Date.now() });
  }

  setVisible(visible: boolean): void {
    this._visible = visible;
    this._render();
  }

  /** Called by WSR's camera height polling to update altitude-gated display */
  refreshAltitudeGate(): void {
    this._render();
  }

  teardown(): void {
    if (this._collection && this._ctx) {
      try { this._ctx.scene.primitives.remove(this._collection); } catch { /* ok */ }
    }
    this._collection = null;
    this._cameras = [];
  }

  private _render(): void {
    const Cesium = this.Cesium;
    const bb = this._collection as {
      removeAll: () => void;
      add: (o: unknown) => void;
      show: boolean;
    } | null;
    if (!bb) return;

    const height = this._getAltitude();
    const shouldShow = this._visible && height < 20000000;
    bb.show = shouldShow;
    if (!shouldShow) return;

    bb.removeAll();
    const iconSz = height < 5000 ? 22 : height < 50000 ? 18 : height < 500000 ? 14 : 10;

    for (const cam of this._cameras) {
      bb.add({
        position: Cesium.Cartesian3.fromDegrees(cam.lon, cam.lat, 5),
        image: CCTV_ICON,
        width: iconSz,
        height: iconSz,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        id: { _wv: true, _camera: cam, id: cam.id, name: cam.name, type: 'cctv', lat: cam.lat, lon: cam.lon, altitude: 5 },
      });
    }
  }
}
