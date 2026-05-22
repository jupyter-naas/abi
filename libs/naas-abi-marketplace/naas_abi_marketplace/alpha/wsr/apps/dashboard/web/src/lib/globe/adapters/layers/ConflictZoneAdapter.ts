/**
 * ConflictZoneAdapter
 *
 * Realizes: wv:ConflictZoneLoadingProcess
 * ICE consumed: wv:ConflictSiteRecord[] from /api/conflict-events
 * Sites rendered: wv:NuclearFacilitySite, wv:MilitaryBaseSite,
 *                 wv:NavalOperatingArea, wv:ConflictZone
 *
 * Severity → color mapping mirrors the threat severity quality
 * (wv:ThreatSeverityLevel) defined in the ontology.
 */

import { GlobeLayerBase } from '../GlobeLayerBase';
import type { GlobeLayerConfiguration } from '../../ports/IGlobeLayerPort';
import type { ProcessType } from '@/lib/ontology';
import type { ConflictEvent } from '@/lib/types';

export class ConflictZoneAdapter extends GlobeLayerBase<ConflictEvent[]> {
  readonly layerId = 'conflict-zone-layer';
  readonly processType: ProcessType = 'ConflictZoneLoadingProcess';
  readonly configuration: GlobeLayerConfiguration = { visible: true, staticLayer: true };

  private _entities: unknown[] = [];

  async initialize(): Promise<void> {
    // Data is pushed via update() by ConflictEventDataSource
    // No self-initialization needed
  }

  update(events: ConflictEvent[]): void {
    const Cesium = this.Cesium;
    const viewer = this.viewer as { entities: { add: (e: unknown) => unknown; remove: (e: unknown) => void } };

    // Remove stale entities
    this._entities.forEach((e) => viewer.entities.remove(e));
    this._entities = [];

    for (const ev of events) {
      const color = this._severityColor(ev.type, ev.severity);
      const radius = ev.severity === 'critical' ? 35000 : ev.severity === 'high' ? 22000 : 14000;
      const pos = Cesium.Cartesian3.fromDegrees(ev.lon, ev.lat, 0);

      const ring = viewer.entities.add({
        position: pos,
        ellipse: {
          semiMinorAxis: radius,
          semiMajorAxis: radius,
          height: 0,
          material: Cesium.Color.fromCssColorString(color).withAlpha(0.12),
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString(color).withAlpha(0.7),
          outlineWidth: ev.severity === 'critical' ? 2 : 1,
        },
      });

      const label = viewer.entities.add({
        position: pos,
        label: {
          text: ev.name,
          font: '10px monospace',
          fillColor: Cesium.Color.fromCssColorString(color),
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cesium.Cartesian2(0, -radius / 5000 - 14),
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          translucencyByDistance: new Cesium.NearFarScalar(50000, 1.0, 4000000, 0.0),
        },
      });

      this._entities.push(ring, label);
    }
  }

  setVisible(visible: boolean): void {
    for (const e of this._entities) {
      (e as { show: boolean }).show = visible;
    }
  }

  teardown(): void {
    const viewer = this._ctx?.viewer as
      | { entities: { remove: (e: unknown) => void } }
      | null;
    if (viewer) {
      this._entities.forEach((e) => { try { viewer.entities.remove(e); } catch { /* ok */ } });
    }
    this._entities = [];
  }

  private _severityColor(type: ConflictEvent['type'], severity: ConflictEvent['severity']): string {
    if (severity === 'critical') return type === 'nuclear' ? '#ffe000' : '#ff2200';
    if (severity === 'high') return type === 'naval' ? '#00cfff' : '#ff6600';
    return '#ffaa00';
  }
}
