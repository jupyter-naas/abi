/**
 * ICesiumContextPort
 *
 * The "Services container" analog from naas-abi-core IEngine.Services.
 * Passed to every IGlobeLayerPort adapter after the Cesium viewer is ready,
 * exactly as set_services() injects the ServicesContainer into modules.
 *
 * Adapters MUST NOT import Cesium directly — they receive it through this
 * context so the engine can mock/swap the renderer in tests without
 * touching adapter code.
 *
 * BFO mapping: concretizes wv:GlobeRenderingProcess (BFO_0000015)
 */

export type CesiumType = typeof import('cesium');

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CesiumViewer = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type CesiumScene  = any;

export interface ICesiumContextPort {
  /** The live Cesium module — use for all `new Cesium.Xxx` calls */
  readonly Cesium: CesiumType;
  /** The live Viewer instance */
  readonly viewer: CesiumViewer;
  /** Convenience: `viewer.scene` */
  readonly scene: CesiumScene;
  /** True once the viewer has fully initialised */
  readonly ready: boolean;
}

/**
 * Protocol analog to ServicesAware in naas-abi-core.
 * Every adapter that needs Cesium access implements this.
 * GlobeEngine calls injectContext() immediately after initialization.
 */
export interface ICesiumContextAware {
  injectContext(ctx: ICesiumContextPort): void;
}

export function isCesiumContextAware(obj: unknown): obj is ICesiumContextAware {
  return typeof obj === 'object' && obj !== null && 'injectContext' in obj;
}
