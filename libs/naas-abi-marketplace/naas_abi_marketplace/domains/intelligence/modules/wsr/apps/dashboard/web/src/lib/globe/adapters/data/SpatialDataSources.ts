/**
 * SpatialDataSources
 *
 * Secondary adapters for static/slow-changing spatial data:
 *   - EarthquakeDataSource  → wv:EarthquakeEventRecord[] (USGS, 5min)
 *   - CCTVDataSource        → wv:OntologyCCTVCameraUnit[] (5min)
 *   - ConflictEventDataSource → wv:ConflictSiteRecord[] (static, loaded once)
 */

import { DataSourceBase } from '../../ports/IDataSourcePort';
import type { GDCType } from '@/lib/ontology';
import type { EarthquakeFeature, CCTVCamera, ConflictEvent } from '@/lib/types';
import { WSR_PROCESSES } from '@/lib/ontology';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

// ─── Earthquake ───────────────────────────────────────────────────────────────

export class EarthquakeDataSource extends DataSourceBase<EarthquakeFeature[]> {
  readonly dataSourceId = 'EarthquakeDataSource';
  readonly gdcType: GDCType = 'EarthquakeEventRecord';
  readonly refreshIntervalMs = WSR_PROCESSES.EarthquakeMonitoringProcess.refreshIntervalMs!;
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['earthquake-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<EarthquakeFeature[]> {
    const res = await fetch(`${API_BASE}/api/earthquakes`, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) throw new Error(`/api/earthquakes ${res.status}`);
    return res.json();
  }
}

// ─── CCTV ────────────────────────────────────────────────────────────────────

export class CCTVDataSource extends DataSourceBase<CCTVCamera[]> {
  readonly dataSourceId = 'CCTVDataSource';
  readonly gdcType: GDCType = 'VideoStream';
  readonly refreshIntervalMs = 300_000; // 5 min — wv:CCTVStreamingProcess cacheTTL
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['cctv-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<CCTVCamera[]> {
    const res = await fetch(`${API_BASE}/api/cctv`, { signal: AbortSignal.timeout(15000) });
    if (!res.ok) throw new Error(`/api/cctv ${res.status}`);
    return res.json();
  }
}

// ─── Conflict Events (static — loaded once, large TTL) ────────────────────────

export class ConflictEventDataSource extends DataSourceBase<ConflictEvent[]> {
  readonly dataSourceId = 'ConflictEventDataSource';
  readonly gdcType: GDCType = 'ConflictSiteRecord';
  // Very long interval — static data; effectively "load once at boot"
  readonly refreshIntervalMs = 3_600_000;
  readonly targetLayerIds: readonly string[];

  constructor(targetLayerIds: string[] = ['conflict-zone-layer']) {
    super();
    this.targetLayerIds = targetLayerIds;
  }

  protected async doFetch(): Promise<ConflictEvent[]> {
    const res = await fetch(`${API_BASE}/api/conflict-events`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`/api/conflict-events ${res.status}`);
    return res.json();
  }
}
