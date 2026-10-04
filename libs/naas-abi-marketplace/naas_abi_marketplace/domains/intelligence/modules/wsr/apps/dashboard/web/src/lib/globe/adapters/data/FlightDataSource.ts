/**
 * FlightDataSource
 *
 * Secondary adapter for wv:FlightTrackingProcess.
 * Fetches wv:AircraftPositionReport[] from /api/flights (OpenSky via server route).
 * Dispatches to 'flight-layer' every 30s.
 *
 * Mirrors the secondary adapter pattern (e.g., Oxigraph.py):
 * implements the port contract without knowing anything about rendering.
 */

import { DataSourceBase } from '../../ports/IDataSourcePort';
import type { GDCType } from '@/lib/ontology';
import type { FlightState } from '@/lib/types';
import { WSR_PROCESSES } from '@/lib/ontology';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

export class FlightDataSource extends DataSourceBase<FlightState[]> {
  readonly dataSourceId = 'FlightDataSource';
  readonly gdcType: GDCType = 'AircraftPositionReport';
  readonly refreshIntervalMs = WSR_PROCESSES.FlightTrackingProcess.refreshIntervalMs!;
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['flight-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<FlightState[]> {
    const res = await fetch(`${API_BASE}/api/flights`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`/api/flights ${res.status}`);
    return res.json();
  }
}

export class MilitaryDataSource extends DataSourceBase<FlightState[]> {
  readonly dataSourceId = 'MilitaryDataSource';
  readonly gdcType: GDCType = 'MilitaryAircraftReport';
  readonly refreshIntervalMs = 60_000;
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['military-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<FlightState[]> {
    const res = await fetch(`${API_BASE}/api/military`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`/api/military ${res.status}`);
    return res.json();
  }
}

export class TheaterAircraftDataSource extends DataSourceBase<FlightState[]> {
  readonly dataSourceId = 'TheaterAircraftDataSource';
  readonly gdcType: GDCType = 'MilitaryAircraftReport';
  readonly refreshIntervalMs = WSR_PROCESSES.TheaterAircraftMonitoringProcess.refreshIntervalMs!;
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['theater-aircraft-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<FlightState[]> {
    const res = await fetch(`${API_BASE}/api/mideast-aircraft`, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) throw new Error(`/api/mideast-aircraft ${res.status}`);
    return res.json();
  }
}
