/** Cockpit-aligned graph parameters for the ontology class canvas. */

let GRAPH_PARAM_DEFS = {};
let VIEW_DEFAULT_OVERRIDES = { "2d": {} };
let PARAMS_KEY = "people-ontology-graph-params-v2";
let MIN_SCALE = 0.25;
let MAX_SCALE = 2.5;

export const graphParams = {
  physics: true,
  clusterBy: "bucket",
  clusterPull: 50,
  linkDistance: 130,
  repulsion: 6400,
  nodeMinGap: 60,
  settleMs: 3000,
  legend: true,
  zoom: 0.82,
  toolbarLayout: "row",
};

function defaultParams() {
  const base = Object.fromEntries(
    Object.entries(GRAPH_PARAM_DEFS).map(([key, def]) => [key, def.default]),
  );
  return { ...base, ...(VIEW_DEFAULT_OVERRIDES["2d"] || {}) };
}

function coerceParams(stored) {
  const params = defaultParams();
  for (const [key, def] of Object.entries(GRAPH_PARAM_DEFS)) {
    const value = stored?.[key];
    if (def.type === "toggle") {
      if (typeof value === "boolean") params[key] = value;
    } else if (def.type === "select") {
      if (def.options.some((option) => option.value === value)) params[key] = value;
    } else if (Number.isFinite(value)) {
      params[key] = Math.min(def.max, Math.max(def.min, value));
    }
  }
  return params;
}

export function readStoredParams() {
  try {
    return coerceParams(JSON.parse(sessionStorage.getItem(PARAMS_KEY) || "{}"));
  } catch {
    return defaultParams();
  }
}

export function persistParams(params) {
  try {
    sessionStorage.setItem(PARAMS_KEY, JSON.stringify(params));
  } catch {
    /* ignore */
  }
}

export function resetParamsToDefaults() {
  const params = defaultParams();
  Object.assign(graphParams, params);
  persistParams(params);
  return params;
}

export function configureOntologyGraph(config) {
  const graph = config?.graph || {};
  MIN_SCALE = graph.scale?.min ?? MIN_SCALE;
  MAX_SCALE = graph.scale?.max ?? MAX_SCALE;
  if (graph.parameters) GRAPH_PARAM_DEFS = graph.parameters;
  if (graph.view_defaults) VIEW_DEFAULT_OVERRIDES = graph.view_defaults;
  if (graph.params_session_key) PARAMS_KEY = graph.params_session_key;
  Object.assign(graphParams, readStoredParams());
}

export function getScaleLimits() {
  return { min: MIN_SCALE, max: MAX_SCALE };
}

export function formatParamValue(key, value) {
  const def = GRAPH_PARAM_DEFS[key];
  if (!def) return String(value);
  const unit = def.unit || "";
  return def.step < 1 ? `${Number(value).toFixed(2)}${unit}` : `${value}${unit}`;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderParamsPanel(params, open) {
  const rows = Object.entries(GRAPH_PARAM_DEFS)
    .map(([key, def]) => {
      if (def.type === "select") {
        const options = def.options
          .map(
            (option) =>
              `<option value="${esc(option.value)}"${params[key] === option.value ? " selected" : ""}>${esc(option.label)}</option>`,
          )
          .join("");
        return `<label class="graph-param">
          <span class="graph-param-head">${esc(def.label)}</span>
          <select data-param="${key}">${options}</select>
          <em>${esc(def.hint)}</em>
        </label>`;
      }
      if (def.type === "toggle") {
        return `<label class="graph-param graph-param-toggle">
          <span class="graph-param-head">${esc(def.label)}
            <input type="checkbox" data-param="${key}" ${params[key] ? "checked" : ""} />
          </span>
          <em>${esc(def.hint)}</em>
        </label>`;
      }
      return `<label class="graph-param">
        <span class="graph-param-head">${esc(def.label)} <strong data-param-value="${key}">${esc(formatParamValue(key, params[key]))}</strong></span>
        <input type="range" data-param="${key}" min="${def.min}" max="${def.max}" step="${def.step}" value="${params[key]}" />
        <em>${esc(def.hint)}</em>
      </label>`;
    })
    .join("");

  return `<div class="graph-params">
    <button type="button" class="graph-params-toggle ontology-graph-params-toggle"
      aria-expanded="${open ? "true" : "false"}" aria-haspopup="true"
      title="Graph parameters" aria-label="Graph parameters">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
      </svg>
    </button>
    <div class="graph-params-menu ontology-graph-params-menu" ${open ? "" : "hidden"}>
      <p class="graph-params-note">Flat class graph. Drag the background to pan, drag a node to move it, scroll to zoom.</p>
      <div class="graph-params-grid">${rows}</div>
      <button type="button" class="ontology-graph-params-reset" id="graph-params-reset">Reset to defaults</button>
    </div>
  </div>`;
}

export function syncParamValueLabels(root, params) {
  for (const [key, def] of Object.entries(GRAPH_PARAM_DEFS)) {
    if (def.type === "range" || (!def.type && def.min != null)) {
      const el = root.querySelector(`[data-param-value="${key}"]`);
      if (el) el.textContent = formatParamValue(key, params[key]);
    }
  }
}
