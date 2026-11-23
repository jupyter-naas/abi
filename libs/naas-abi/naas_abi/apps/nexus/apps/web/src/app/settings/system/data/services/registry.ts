/**
 * Service views by API name; unknown services get a sensible generic view. Each view
 * (and its stylesheet) loads when its service's page first opens (#1609): a page never
 * brings the code of the fifteen others. The sidebar and Recent changes name and draw
 * a service from `lib/nav.ts` and `lib/service-pages.ts`, without loading its view.
 */
import { useEffect, useState } from 'react';
import { Database } from 'lucide-react';
import type { ServiceView } from './types';

const LOADERS: Record<string, () => Promise<ServiceView>> = {
  object_storage: () => import('./object-storage').then((m) => m.objectStorageView),
  secret: () => import('./secret').then((m) => m.secretView),
  keyvalue: () => import('./keyvalue').then((m) => m.keyValueView),
  cache: () => import('./cache').then((m) => m.cacheView),
  document: () => import('./document').then((m) => m.documentView),
  vector_store: () => import('./vector-store').then((m) => m.vectorStoreView),
  triple_store: () => import('./triple-store').then((m) => m.tripleStoreView),
  dataset: () => import('./dataset').then((m) => m.datasetView),
  source_control: () => import('./source-control').then((m) => m.sourceControlView),
  coding_environment: () => import('./coding-environment').then((m) => m.codingEnvironmentView),
  model_registry: () => import('./model-registry').then((m) => m.modelRegistryView),
  email: () => import('./email').then((m) => m.emailView),
  event: () => import('./event').then((m) => m.eventView),
  activity_log: () => import('./activity-log').then((m) => m.activityLogView),
  bus: () => import('./bus').then((m) => m.busView),
  discovery: () => import('./discovery').then((m) => m.discoveryView),
};

/** The services with a view of their own. */
export const SERVICE_VIEW_NAMES: readonly string[] = Object.keys(LOADERS);

/** Views loaded so far (at most one per service, so bounded by the services). */
const LOADED = new Map<string, ServiceView>();
const PENDING = new Map<string, Promise<ServiceView>>();

export function registerServiceView(view: ServiceView): void {
  LOADED.set(view.name, view);
}

export function genericView(name: string): ServiceView {
  const label = name.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  return {
    name,
    label,
    description: `Data held by the ${label.toLowerCase()} service.`,
    icon: Database,
    noun: { one: 'entry', many: 'entries' },
    editor: { language: () => 'plaintext' },
  };
}

/** The view of ``name`` if it is ready (loaded, or generic), else null until it loads. */
export function loadedServiceView(name: string): ServiceView | null {
  return LOADED.get(name) ?? (LOADERS[name] ? null : genericView(name));
}

/** Loads the view of ``name`` once; callers at the same time share one import. */
export function loadServiceView(name: string): Promise<ServiceView> {
  const ready = loadedServiceView(name);
  if (ready) return Promise.resolve(ready);
  const pending = PENDING.get(name);
  if (pending) return pending;
  const load = LOADERS[name]()
    .then((view) => {
      LOADED.set(name, view);
      return view;
    })
    .finally(() => PENDING.delete(name));
  PENDING.set(name, load);
  return load;
}

/**
 * The view of ``service``, loading it on first use: ``view`` is null while its code
 * loads; ``failed`` says it could not be loaded (never a generic stand-in for a known
 * service: the secret view masks what the generic one would show).
 */
export function useServiceView(service: string): { view: ServiceView | null; failed: boolean } {
  const [state, setState] = useState<{ service: string; view: ServiceView | null; failed: boolean }>(() => ({
    service,
    view: loadedServiceView(service),
    failed: false,
  }));
  const current = state.service === service ? state : { service, view: loadedServiceView(service), failed: false };
  const settled = current.view !== null || current.failed;
  useEffect(() => {
    if (settled) return;
    let live = true;
    loadServiceView(service).then(
      (view) => live && setState({ service, view, failed: false }),
      () => live && setState({ service, view: null, failed: true }),
    );
    return () => {
      live = false;
    };
  }, [service, settled]);
  return { view: current.view, failed: current.failed };
}
