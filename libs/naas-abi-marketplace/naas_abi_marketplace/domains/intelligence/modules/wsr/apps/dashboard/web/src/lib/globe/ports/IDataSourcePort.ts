/**
 * IDataSourcePort — Secondary Port for External Data Sources
 *
 * Mirrors ITripleStorePort / IObjectStorageAdapter from naas-abi-core:
 * the technology-agnostic contract that each data fetching adapter must
 * satisfy. GlobeEngine knows only this interface — it doesn't care
 * whether data comes from OpenSky, airplanes.live, USGS, or a static file.
 *
 * One data source adapter = one wv:InformationContentEntity type.
 * The GDC it produces is dispatched to all declared target layers.
 *
 * Polling lifecycle:
 *   GlobeEngine.startPolling() calls fetch() on the declared interval,
 *   then dispatches the result to targetLayerIds via IGlobeLayerPort.update().
 *   This mirrors the OntologyEvent pub/sub trigger pattern in naas-abi-core.
 */

import type { GDCType } from '@/lib/ontology';

// ─── Provenance envelope (analog to the OntologyReasoner canonicalization) ────

export interface DataSourceResult<T> {
  /** The strongly-typed ICE payload */
  readonly data: T;
  /** Unix ms — when this fetch completed */
  readonly fetchedAt: number;
  /** wvi: IRI of the endpoint that produced this data */
  readonly sourceEndpointIri: string;
  /** Ontology GDC type produced */
  readonly gdcType: GDCType;
  /** Whether the data changed since the last fetch (for diff optimisation) */
  readonly changed: boolean;
}

// ─── Primary port ─────────────────────────────────────────────────────────────

/**
 * IDataSourcePort<T>
 *
 * T = the ICE array or object produced by this adapter.
 * e.g. FlightDataSource implements IDataSourcePort<AircraftPositionReport[]>
 */
export interface IDataSourcePort<T = unknown> {
  /** Unique stable identifier — used as registry key in GlobeEngine */
  readonly dataSourceId: string;

  /**
   * The GDC type produced by this adapter.
   * Must match an entry in the wsr ontology.
   */
  readonly gdcType: GDCType;

  /**
   * Polling interval in ms. Mirrors wv:hasRefreshInterval.
   * GlobeEngine uses this to schedule fetch() calls.
   */
  readonly refreshIntervalMs: number;

  /**
   * layerIds that this data source feeds.
   * GlobeEngine calls layer.update(data) for each after fetch().
   * Analog to topic routing in BusPorts: one publish → many subscribers.
   */
  readonly targetLayerIds: readonly string[];

  /**
   * Fetch fresh data from the external source.
   * Should never throw — return the last cached result on error.
   */
  fetch(): Promise<DataSourceResult<T>>;

  /**
   * Last successful result — allows GlobeEngine to replay data to a
   * newly registered layer without waiting for the next poll cycle.
   * Analog to querying the triple store for current state.
   */
  getLastResult(): DataSourceResult<T> | null;
}

// ─── Abstract base (mirrors ServiceBase from naas-abi-core) ──────────────────

export abstract class DataSourceBase<T> implements IDataSourcePort<T> {
  abstract readonly dataSourceId: string;
  abstract readonly gdcType: GDCType;
  abstract readonly refreshIntervalMs: number;
  abstract readonly targetLayerIds: readonly string[];

  protected _lastResult: DataSourceResult<T> | null = null;

  protected abstract doFetch(): Promise<T>;

  async fetch(): Promise<DataSourceResult<T>> {
    try {
      const data = await this.doFetch();
      const result: DataSourceResult<T> = {
        data,
        fetchedAt: Date.now(),
        sourceEndpointIri: this.sourceEndpointIri,
        gdcType: this.gdcType,
        changed: this.hasChanged(data),
      };
      this._lastResult = result;
      return result;
    } catch {
      if (this._lastResult) return { ...this._lastResult, changed: false };
      const empty: DataSourceResult<T> = {
        data: [] as unknown as T,
        fetchedAt: Date.now(),
        sourceEndpointIri: this.sourceEndpointIri,
        gdcType: this.gdcType,
        changed: false,
      };
      return empty;
    }
  }

  getLastResult(): DataSourceResult<T> | null {
    return this._lastResult;
  }

  /** Override to provide exact wvi: endpoint IRI */
  protected get sourceEndpointIri(): string {
    return `http://ontology.naas.ai/wsr/instances/${this.dataSourceId}`;
  }

  /** Override for change detection logic */
  protected hasChanged(_newData: T): boolean {
    return true; // Default: always dispatch
  }
}
