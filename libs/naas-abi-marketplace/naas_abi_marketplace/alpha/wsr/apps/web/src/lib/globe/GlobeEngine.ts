/**
 * GlobeEngine — The Hexagonal Core
 *
 * Direct analog to naas-abi-core Engine.py:
 *
 *   Engine          → GlobeEngine
 *   IEngine.Services → ICesiumContextPort        (injected into every adapter)
 *   BaseModule       → IGlobeLayerPort adapter    (one per BFO process type)
 *   Integration      → IDataSourcePort adapter    (one per ICE type)
 *   EngineModuleLoader → GlobeEngine.initialize() (topological: ctx first, then layers)
 *   OntologyEvent bus  → GlobeEventBus           (click/hover/flyto dispatch)
 *   Services.wire_services() → injectContext()   (adapter receives context after all are registered)
 *
 * The engine knows NOTHING about Cesium API specifics — it only holds
 * the ICesiumContextPort reference and dispatches it. All Cesium code
 * lives exclusively inside adapter implementations.
 *
 * Usage:
 *   const engine = new GlobeEngine();
 *   engine
 *     .registerLayer(new BorderLayerAdapter())
 *     .registerLayer(new FlightLayerAdapter())
 *     .registerDataSource(new FlightDataSource(['flight-layer']));
 *
 *   await engine.initialize(Cesium, viewer);   // boot: context → layers → sources
 *   // ... polling runs automatically ...
 *   engine.teardown();                          // cleanup on unmount
 */

import type { IGlobeLayerPort, GlobeEvent, GlobeEventHandler, GlobeEventType } from './ports/IGlobeLayerPort';
import type { IDataSourcePort } from './ports/IDataSourcePort';
import type { ICesiumContextPort } from './ports/ICesiumContextPort';
import { isCesiumContextAware } from './ports/ICesiumContextPort';

// ─── Engine state ──────────────────────────────────────────────────────────────

type EngineStatus = 'uninitialized' | 'initializing' | 'ready' | 'torn-down';

// ─── Event bus (analog to BusService + IBusAdapter) ──────────────────────────

class GlobeEventBus {
  private handlers = new Map<string, Set<GlobeEventHandler>>();

  subscribe(layerId: string, type: GlobeEventType, handler: GlobeEventHandler): void {
    const key = `${layerId}:${type}`;
    if (!this.handlers.has(key)) this.handlers.set(key, new Set());
    this.handlers.get(key)!.add(handler);
  }

  /** Subscribe to all events of a type regardless of source layer */
  subscribeGlobal(type: GlobeEventType, handler: GlobeEventHandler): void {
    this.subscribe('*', type, handler);
  }

  publish(event: GlobeEvent): void {
    // Layer-specific handlers
    const key = `${event.layerId}:${event.type}`;
    this.handlers.get(key)?.forEach((h) => h(event));
    // Global handlers
    const globalKey = `*:${event.type}`;
    this.handlers.get(globalKey)?.forEach((h) => h(event));
  }

  clear(): void {
    this.handlers.clear();
  }
}

// ─── GlobeEngine ──────────────────────────────────────────────────────────────

export class GlobeEngine {
  private status: EngineStatus = 'uninitialized';

  /** Registered layer adapters — analog to Engine.modules */
  private readonly layers = new Map<string, IGlobeLayerPort>();

  /** Registered data source adapters — analog to Engine integrations */
  private readonly dataSources = new Map<string, IDataSourcePort>();

  /** Polling timers — one per data source */
  private readonly pollingTimers = new Map<string, ReturnType<typeof setInterval>>();

  /** Shared Cesium context — injected into every adapter after initialization */
  private context: ICesiumContextPort | null = null;

  /** Event bus — analog to BusService */
  readonly events = new GlobeEventBus();

  // ─── Registration API (analog to Engine.load() module registration) ────────

  /**
   * Register a layer adapter.
   * Must be called BEFORE initialize().
   * Analog to listing a module in config.yaml.
   */
  registerLayer(layer: IGlobeLayerPort): this {
    if (this.status !== 'uninitialized') {
      console.warn(`[GlobeEngine] Cannot register layer "${layer.layerId}" after initialization`);
      return this;
    }
    this.layers.set(layer.layerId, layer);

    // Wire the adapter's emit() method to the engine event bus
    layer.onEvent = (type, handler) => {
      this.events.subscribe(layer.layerId, type, handler);
    };
    layer.emit = (event) => {
      this.events.publish(event);
    };

    return this;
  }

  /**
   * Register a data source adapter.
   * Must be called BEFORE initialize().
   */
  registerDataSource<T>(ds: IDataSourcePort<T>): this {
    if (this.status !== 'uninitialized') {
      console.warn(`[GlobeEngine] Cannot register data source "${ds.dataSourceId}" after initialization`);
      return this;
    }
    this.dataSources.set(ds.dataSourceId, ds as IDataSourcePort);
    return this;
  }

  // ─── Lifecycle ─────────────────────────────────────────────────────────────

  /**
   * Boot sequence — mirrors Engine.load():
   *   1. Build ICesiumContextPort from viewer
   *   2. Inject context into all adapters (wire_services analog)
   *   3. Call initialize() on each layer in registration order
   *   4. Replay any cached data source results to newly initialized layers
   *   5. Start polling timers for all data sources
   */
  async initialize(
    Cesium: typeof import('cesium'),
    viewer: unknown,
  ): Promise<void> {
    if (this.status !== 'uninitialized') {
      console.warn('[GlobeEngine] initialize() called more than once');
      return;
    }
    this.status = 'initializing';

    // Build the context (Services container analog)
    this.context = {
      Cesium,
      viewer,
      scene: (viewer as { scene: unknown }).scene,
      ready: true,
    };

    // Step 1: inject context into all adapters (wire_services analog)
    for (const layer of this.layers.values()) {
      if (isCesiumContextAware(layer)) {
        layer.injectContext(this.context);
      }
    }

    // Step 2: initialize layers in registration order (on_load analog)
    for (const layer of this.layers.values()) {
      try {
        await layer.initialize();
      } catch (err) {
        console.error(`[GlobeEngine] Layer "${layer.layerId}" failed to initialize:`, err);
      }
    }

    // Step 3: start polling (analog to engine starting scheduled pipelines)
    for (const ds of this.dataSources.values()) {
      this.startPolling(ds);
    }

    this.status = 'ready';
  }

  /**
   * Cleanup — mirrors Engine.on_unloaded():
   *   1. Stop all polling timers
   *   2. Call teardown() on each layer (removes Cesium primitives)
   *   3. Clear event bus
   */
  teardown(): void {
    this.status = 'torn-down';

    for (const timer of this.pollingTimers.values()) {
      clearInterval(timer);
    }
    this.pollingTimers.clear();

    for (const layer of this.layers.values()) {
      try {
        layer.teardown();
      } catch (err) {
        console.error(`[GlobeEngine] Layer "${layer.layerId}" teardown error:`, err);
      }
    }

    this.events.clear();
    this.context = null;
  }

  // ─── Runtime control API ───────────────────────────────────────────────────

  /**
   * Toggle layer visibility.
   * Analog to toggling entity.show in the triple store.
   */
  setLayerVisible(layerId: string, visible: boolean): void {
    this.layers.get(layerId)?.setVisible(visible);
    this.events.publish({
      type: 'layer:visibility-changed',
      layerId,
      payload: { visible },
      timestamp: Date.now(),
    });
  }

  /**
   * Push data to a specific layer directly (for use by external hooks).
   * Analog to calling TripleStoreService.insert() directly.
   */
  updateLayer<T>(layerId: string, data: T): void {
    const layer = this.layers.get(layerId);
    if (layer) (layer as IGlobeLayerPort<T>).update(data);
  }

  /**
   * Force an immediate fetch on a specific data source.
   * Analog to manually triggering a pipeline.
   */
  async triggerDataSource(dataSourceId: string): Promise<void> {
    const ds = this.dataSources.get(dataSourceId);
    if (!ds) return;
    const result = await ds.fetch();
    this.dispatchToLayers(ds, result.data);
  }

  getLayer(layerId: string): IGlobeLayerPort | undefined {
    return this.layers.get(layerId);
  }

  get isReady(): boolean {
    return this.status === 'ready';
  }

  // ─── Internal polling ──────────────────────────────────────────────────────

  private startPolling(ds: IDataSourcePort): void {
    // Initial fetch immediately
    this.fetchAndDispatch(ds);

    // Then schedule repeating
    const timer = setInterval(
      () => this.fetchAndDispatch(ds),
      ds.refreshIntervalMs,
    );
    this.pollingTimers.set(ds.dataSourceId, timer);
  }

  private async fetchAndDispatch(ds: IDataSourcePort): Promise<void> {
    try {
      const result = await ds.fetch();
      if (result.changed || !result.fetchedAt) {
        this.dispatchToLayers(ds, result.data);
      }
    } catch (err) {
      console.warn(`[GlobeEngine] Data source "${ds.dataSourceId}" fetch error:`, err);
    }
  }

  private dispatchToLayers(ds: IDataSourcePort, data: unknown): void {
    for (const layerId of ds.targetLayerIds) {
      const layer = this.layers.get(layerId);
      if (layer) {
        try {
          layer.update(data);
        } catch (err) {
          console.error(`[GlobeEngine] Dispatch to layer "${layerId}" failed:`, err);
        }
      }
    }
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createGlobeEngine(): GlobeEngine {
  return new GlobeEngine();
}
