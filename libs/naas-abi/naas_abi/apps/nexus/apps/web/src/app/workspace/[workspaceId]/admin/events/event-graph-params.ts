/**
 * Graph parameters, ported from the Personnel Cockpit's `graph.parameters`
 * config block (`domains/personnel/apps/cockpit/config.yaml`).
 *
 * The cockpit reads these from YAML at runtime; Nexus has no per-app config
 * file for the admin surface, so the same definitions live here as data. Keep
 * the shapes identical — the panel renders straight off them.
 */

export type GraphView = '2d' | '3d';

export const GRAPH_VIEWS: GraphView[] = ['2d', '3d'];

export const GRAPH_VIEW_LABELS: Record<GraphView, string> = {
  '2d': '2D view',
  '3d': '3D view',
};

export type ParamDef =
  | { label: string; type: 'toggle'; default: boolean; hint: string }
  | {
      label: string;
      type: 'select';
      default: string;
      options: { value: string; label: string }[];
      hint: string;
    }
  | {
      label: string;
      type?: 'range';
      min: number;
      max: number;
      step: number;
      default: number;
      unit: string;
      hint: string;
    };

/** How many processes the graph pulls in. The cockpit's "distance" slider. */
export const PROCESS_COUNT_DEF = {
  label: 'Processes',
  min: 1,
  max: 24,
  step: 1,
  default: 8,
  unit: '',
  hint: 'How many of the most recent matching processes to draw. Each one fans out into its own BFO buckets; shared participants, sites and tools are drawn once.',
} as const;

export const GRAPH_PARAM_DEFS: Record<string, ParamDef> = {
  toolbarLayout: {
    label: 'Toolbar layout',
    type: 'select',
    default: 'row',
    options: [
      { value: 'row', label: 'Horizontal' },
      { value: 'column', label: 'Vertical' },
    ],
    hint: 'Arrange search and filters in a row or a column.',
  },
  physics: { label: 'Physics', type: 'toggle', default: true, hint: 'Run the force simulation.' },
  clusterBy: {
    label: 'Cluster by',
    type: 'select',
    default: 'process',
    options: [
      { value: 'none', label: 'Nothing' },
      { value: 'process', label: 'Process' },
      { value: 'bucket', label: 'BFO bucket' },
    ],
    hint: 'Pull related nodes into groups.',
  },
  clusterPull: { label: 'Cluster pull', min: 0, max: 100, step: 5, default: 50, unit: '%', hint: 'How tightly each group is drawn together.' },
  linkDistance: { label: 'Link length', min: 80, max: 520, step: 10, default: 260, unit: 'px', hint: 'Target distance between connected nodes.' },
  repulsion: { label: 'Repulsion', min: 200, max: 9000, step: 100, default: 3200, unit: '', hint: 'How strongly nodes push away from one another.' },
  nodeMinGap: { label: 'Node spacing', min: 0, max: 180, step: 5, default: 60, unit: 'px', hint: 'Minimum gap between nodes.' },
  settleMs: { label: 'Settle time', min: 500, max: 12000, step: 500, default: 3000, unit: 'ms', hint: 'How long nodes move before the layout freezes.' },
  legend: { label: 'BFO legend', type: 'toggle', default: false, hint: 'Show the BFO colour key.' },
  zoom: { label: 'Default zoom', min: 0.25, max: 2.5, step: 0.05, default: 1, unit: '×', hint: 'Initial and reset canvas scale.' },
};

/** Overrides applied when the view is switched, mirroring `view_defaults`. */
export const VIEW_DEFAULTS: Record<GraphView, Record<string, string | number | boolean>> = {
  '2d': { clusterBy: 'bucket', nodeMinGap: 150, zoom: 0.75, legend: false, toolbarLayout: 'row' },
  '3d': { clusterBy: 'bucket', linkDistance: 300, repulsion: 4500, nodeMinGap: 150, settleMs: 3000, zoom: 0.6, legend: false, toolbarLayout: 'row' },
};

export const DEFAULT_VIEW: GraphView = '3d';

export interface GraphParams {
  view: GraphView;
  processCount: number;
  toolbarLayout: string;
  physics: boolean;
  clusterBy: string;
  clusterPull: number;
  linkDistance: number;
  repulsion: number;
  nodeMinGap: number;
  settleMs: number;
  legend: boolean;
  zoom: number;
  [key: string]: string | number | boolean;
}

export function defaultGraphParams(view: GraphView): GraphParams {
  const base: Record<string, string | number | boolean> = {};
  for (const [key, def] of Object.entries(GRAPH_PARAM_DEFS)) base[key] = def.default;
  return {
    ...base,
    ...VIEW_DEFAULTS[view],
    view,
    processCount: PROCESS_COUNT_DEF.default,
  } as GraphParams;
}

function clampNumber(value: unknown, def: Extract<ParamDef, { min: number }>): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return def.default;
  return Math.min(def.max, Math.max(def.min, n));
}

/** Keep a stored blob honest: unknown keys dropped, ranges clamped. */
export function coerceGraphParams(view: GraphView, stored: unknown): GraphParams {
  const params = defaultGraphParams(view);
  if (!stored || typeof stored !== 'object') return params;
  const raw = stored as Record<string, unknown>;
  for (const [key, def] of Object.entries(GRAPH_PARAM_DEFS)) {
    if (!(key in raw)) continue;
    if (def.type === 'toggle') params[key] = Boolean(raw[key]);
    else if (def.type === 'select') {
      if (def.options.some((option) => option.value === raw[key])) params[key] = raw[key] as string;
    } else params[key] = clampNumber(raw[key], def);
  }
  if ('processCount' in raw) params.processCount = clampNumber(raw.processCount, PROCESS_COUNT_DEF);
  return params;
}

export function formatParamValue(key: string, value: string | number | boolean): string {
  const def = key === 'processCount' ? PROCESS_COUNT_DEF : GRAPH_PARAM_DEFS[key];
  if (!def || !('min' in def)) return String(value);
  const unit = def.unit || '';
  return def.step < 1 ? `${Number(value).toFixed(2)}${unit}` : `${value}${unit}`;
}

const STORAGE_KEY = 'nexus-events-graph-params-v1';

export function readStoredParams(): GraphParams {
  if (typeof window === 'undefined') return defaultGraphParams(DEFAULT_VIEW);
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultGraphParams(DEFAULT_VIEW);
    const parsed = JSON.parse(raw) as { view?: unknown };
    const view: GraphView = parsed?.view === '2d' || parsed?.view === '3d' ? parsed.view : DEFAULT_VIEW;
    return coerceGraphParams(view, parsed);
  } catch {
    return defaultGraphParams(DEFAULT_VIEW);
  }
}

export function writeStoredParams(params: GraphParams): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  } catch {
    /* non-fatal: private mode or a full quota just means no persistence */
  }
}
