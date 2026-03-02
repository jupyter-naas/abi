/**
 * IGlobeLayerPort — Primary Port for Globe Layer Adapters
 *
 * Mirrors ITripleStorePort / IVectorStorePort from naas-abi-core:
 * a technology-agnostic contract that each concrete Cesium rendering
 * adapter must satisfy.
 *
 * One adapter = one BFO process + its corresponding ICE type.
 * Examples:
 *   - FlightLayerAdapter   realizes wv:FlightTrackingProcess
 *   - ConflictZoneAdapter  realizes wv:ConflictZoneLoadingProcess
 *   - CCTVLayerAdapter     realizes wv:CCTVStreamingProcess
 *
 * Adapters declare which ICE data type they consume (generic T) and
 * which layerId they register under — enforcing the single-responsibility
 * principle at the adapter boundary.
 */

import type { ProcessType } from '@/lib/ontology';
import type { ICesiumContextAware } from './ICesiumContextPort';

// ─── Layer configuration (analog to ModuleConfiguration) ─────────────────────

export interface GlobeLayerConfiguration {
  /** Initial visibility state */
  readonly visible: boolean;
  /**
   * Whether this layer is purely decorative (no data polling).
   * True for borders, city labels, conflict zones loaded once at boot.
   */
  readonly staticLayer?: boolean;
}

// ─── Globe event bus — analog to OntologyEvent + BusPorts ────────────────────

export type GlobeEventType =
  | 'entity:click'
  | 'entity:hover'
  | 'layer:visibility-changed'
  | 'camera:flyto'
  | 'cctv:open'
  /** Emitted by each real-time adapter after update() — payload: { count: number } */
  | 'data:updated';

export interface GlobeEvent<P = unknown> {
  readonly type: GlobeEventType;
  readonly layerId: string;
  readonly payload: P;
  readonly timestamp: number;
}

export type GlobeEventHandler<P = unknown> = (event: GlobeEvent<P>) => void;

// ─── Primary port ─────────────────────────────────────────────────────────────

/**
 * IGlobeLayerPort<T>
 *
 * T = the Information Content Entity type this adapter consumes.
 * e.g. FlightLayerAdapter implements IGlobeLayerPort<FlightState[]>
 *
 * Lifecycle matches BaseModule lifecycle from naas-abi-core:
 *   initialize() → on_load()
 *   teardown()   → on_unloaded()
 *   update()     → the runtime data ingestion path
 */
export interface IGlobeLayerPort<T = unknown> extends ICesiumContextAware {
  /** Unique stable identifier — used as registry key in GlobeEngine */
  readonly layerId: string;

  /**
   * The BFO process this adapter realizes.
   * Must match an entry in WSR_PROCESSES.
   */
  readonly processType: ProcessType;

  /** Configuration declared at registration time */
  readonly configuration: GlobeLayerConfiguration;

  /**
   * Called by GlobeEngine after injectContext() completes.
   * Adapter creates its Cesium primitives / entities here.
   * Analog to BaseModule.on_load().
   */
  initialize(): Promise<void>;

  /**
   * Called by GlobeEngine when new ICE data arrives from a data source.
   * Adapter diffs/updates its Cesium primitives.
   * Analog to Pipeline.run() receiving an RDF graph.
   */
  update(data: T): void;

  /**
   * Toggle layer visibility without destroying primitives.
   * Analog to setting entity.show on a triple-store view.
   */
  setVisible(visible: boolean): void;

  /**
   * Called by GlobeEngine on cleanup (component unmount / hot reload).
   * Adapter removes all its Cesium primitives from the scene.
   */
  teardown(): void;

  /**
   * Subscribe to events produced by this adapter (clicks, hover).
   * Engine routes events to registered handlers.
   * Analog to BusService.subscribe().
   */
  onEvent(type: GlobeEventType, handler: GlobeEventHandler): void;

  /**
   * Publish an event from this adapter to the engine event bus.
   * Engine fans out to all subscribers.
   */
  emit(event: GlobeEvent): void;
}
