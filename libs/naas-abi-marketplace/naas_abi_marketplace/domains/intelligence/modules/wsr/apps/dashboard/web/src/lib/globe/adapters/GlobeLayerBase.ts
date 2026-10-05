/**
 * GlobeLayerBase — Abstract Base for All Cesium Layer Adapters
 *
 * Mirrors ServiceBase from naas-abi-core: provides the injectContext()
 * wiring mechanism and the event bus wiring, so concrete adapters
 * only implement initialize(), update(), setVisible(), teardown().
 *
 * Concrete adapters declare:
 *   readonly layerId = 'my-layer'
 *   readonly processType: ProcessType = 'FlightTrackingProcess'
 *   readonly configuration = { visible: true }
 */

import type { ProcessType } from '@/lib/ontology';
import type {
  IGlobeLayerPort,
  GlobeLayerConfiguration,
  GlobeEvent,
  GlobeEventHandler,
  GlobeEventType,
} from '../ports/IGlobeLayerPort';
import type { ICesiumContextPort } from '../ports/ICesiumContextPort';
import type { CesiumType } from '../ports/ICesiumContextPort';

export abstract class GlobeLayerBase<T = unknown> implements IGlobeLayerPort<T> {
  abstract readonly layerId: string;
  abstract readonly processType: ProcessType;
  abstract readonly configuration: GlobeLayerConfiguration;

  // ─── Cesium context (injected by engine — analog to ServiceBase.services) ──

  protected _ctx: ICesiumContextPort | null = null;

  /** Convenience accessor — asserts context is injected */
  protected get Cesium(): CesiumType {
    if (!this._ctx) throw new Error(`[${this.layerId}] Cesium context not injected — call injectContext() first`);
    return this._ctx.Cesium;
  }

  protected get viewer() {
    if (!this._ctx) throw new Error(`[${this.layerId}] Cesium context not injected`);
    return this._ctx.viewer;
  }

  protected get scene() {
    if (!this._ctx) throw new Error(`[${this.layerId}] Cesium context not injected`);
    return this._ctx.scene;
  }

  injectContext(ctx: ICesiumContextPort): void {
    this._ctx = ctx;
  }

  // ─── Event bus wiring (set by GlobeEngine.registerLayer()) ────────────────

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  onEvent(_type: GlobeEventType, _handler: GlobeEventHandler): void {
    // Replaced by engine.registerLayer() — never called directly
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  emit(_event: GlobeEvent): void {
    // Replaced by engine.registerLayer() — never called directly
  }

  protected emitClick(payload: unknown): void {
    this.emit({ type: 'entity:click', layerId: this.layerId, payload, timestamp: Date.now() });
  }

  protected emitCCTVOpen(payload: unknown): void {
    this.emit({ type: 'cctv:open', layerId: this.layerId, payload, timestamp: Date.now() });
  }

  // ─── Required by each concrete adapter ────────────────────────────────────

  abstract initialize(): Promise<void>;
  abstract update(data: T): void;
  abstract setVisible(visible: boolean): void;
  abstract teardown(): void;
}
