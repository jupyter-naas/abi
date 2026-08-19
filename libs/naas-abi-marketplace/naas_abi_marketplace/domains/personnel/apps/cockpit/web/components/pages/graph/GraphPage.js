/**
 * Graph page - acts of working around a focus person, with labeled relations.
 */

import {
  BFO_SEVEN,
  bfoColor,
  configureBfoBuckets,
} from "../processes/bfo-buckets.js";
import {
  applyDateFilter,
  collectProcessTemporalRecords,
  computeGlobalDateRange,
  configureDateSlicer,
  mountDateRangeSlicer,
  persistDateSlicer,
  renderDateSlicer,
} from "./graph-date-slicer.js";

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const DISTANCE_KEY = "cockpit-graph-distance";
const LAST_PERSON_KEY = "cockpit-graph-last-person";
const HIDDEN_CLASS_TYPES_KEY = "cockpit-graph-hidden-classes";
const HIDDEN_CLASS_INSTANCES_KEY = "cockpit-graph-hidden-class-instances";
const HIDDEN_PROCESS_TYPES_KEY = "cockpit-graph-hidden-process-types";
const HIDDEN_PROCESSES_KEY = "cockpit-graph-hidden-processes";
let MAX_PROCESSES_PER_CLASS;
let MIN_SCALE;
let MAX_SCALE;
let GRAPH_NODE_RADIUS;
let NODE_LABEL_FONT_SIZE;
let NODE_LABEL_LINE_HEIGHT;
let PROCESS_ROOT_RADIUS;
let PARAMS_KEY = "cockpit-graph-params-v2";

/**
 * Live graph parameters. Everything the simulation and the initial view read
 * comes from here rather than from a constant, so the parameters panel can
 * change any of it and repaint without a reload.
 */
let GRAPH_PARAM_DEFS = {};

// Hops are counted from the selected person, who roots the traversal - the
// acts of working are one hop out, not the origin.
let DISTANCE_HINT;

const GRAPH_VIEWS = ["2d", "3d"];
let GRAPH_VIEW_LABELS = {};
let DEFAULT_GRAPH_VIEW = "3d";
let GRAPH_PAGE_URL;
let DEFAULT_ENTITY_SLUG;
let CONFIGURED_PAGE_URLS = new Set();

/**
 * Defaults that differ between the two views. Depth needs more room than the
 * flat view: longer links, stronger repulsion and a wider spacing floor keep
 * clusters legible once they are spread through z, and the simulation is given
 * longer to settle because it has a third axis to resolve.
 */
let GRAPH_VIEW_DEFAULT_OVERRIDES = {};
let DATE_SLICER_CONFIG = configureDateSlicer();

function defaultGraphParams(view) {
  const base = Object.fromEntries(
    Object.entries(GRAPH_PARAM_DEFS).map(([key, def]) => [key, def.default])
  );
  return { ...base, ...(GRAPH_VIEW_DEFAULT_OVERRIDES[view] || {}) };
}

function coerceParams(view, stored) {
  const params = defaultGraphParams(view);
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

/** Each view keeps its own set of values, so switching tabs does not disturb the other. */
function readStoredState() {
  let stored = {};
  try {
    stored = JSON.parse(sessionStorage.getItem(PARAMS_KEY) || "{}");
  } catch {
    // Malformed storage falls back to defaults.
  }
  const view = GRAPH_VIEWS.includes(stored.view) ? stored.view : DEFAULT_GRAPH_VIEW;
  const byView = {};
  for (const name of GRAPH_VIEWS) {
    byView[name] = coerceParams(name, stored.byView?.[name]);
  }
  return { view, byView };
}

let graphState = { view: "2d", byView: { "2d": {}, "3d": {} } };

// Populated from config in configureGraph(). Do not read session storage before then.
const graphParams = { view: "2d" };

function configureGraph(config) {
  const graph = config.graph || {};
  const node = graph.node || {};
  MAX_PROCESSES_PER_CLASS =
    graph.max_processes_per_class ?? MAX_PROCESSES_PER_CLASS ?? 10;
  MIN_SCALE = graph.scale?.min ?? MIN_SCALE;
  MAX_SCALE = graph.scale?.max ?? MAX_SCALE;
  GRAPH_NODE_RADIUS = node.radius ?? GRAPH_NODE_RADIUS;
  NODE_LABEL_FONT_SIZE = node.label_font_size ?? NODE_LABEL_FONT_SIZE;
  NODE_LABEL_LINE_HEIGHT = node.label_line_height ?? NODE_LABEL_LINE_HEIGHT;
  PROCESS_ROOT_RADIUS = node.process_root_radius ?? PROCESS_ROOT_RADIUS;
  CAMERA_DISTANCE = graph.camera_distance ?? CAMERA_DISTANCE;
  DEFAULT_PERSON_LABEL = graph.default_person_label ?? DEFAULT_PERSON_LABEL;
  DEFAULT_DISTANCE = graph.default_distance ?? DEFAULT_DISTANCE;
  DEFAULT_GRAPH_VIEW = GRAPH_VIEWS.includes(graph.default_view)
    ? graph.default_view
    : DEFAULT_GRAPH_VIEW;
  GRAPH_PAGE_URL =
    config.app?.pages?.find((page) => page.page_id === "graph")?.url ||
    GRAPH_PAGE_URL;
  DEFAULT_ENTITY_SLUG =
    config.app?.default_entity?.url_slug || DEFAULT_ENTITY_SLUG;
  CONFIGURED_PAGE_URLS = new Set(
    (config.app?.pages || []).map((page) => page.url)
  );
  if (graph.parameters) GRAPH_PARAM_DEFS = graph.parameters;
  if (graph.view_defaults) GRAPH_VIEW_DEFAULT_OVERRIDES = graph.view_defaults;
  if (graph.params_session_key) PARAMS_KEY = graph.params_session_key;
  DATE_SLICER_CONFIG = configureDateSlicer(graph.date_slicer);
  DISTANCE_HINT = graph.distance_hint;
  GRAPH_VIEW_LABELS = graph.view_labels || {};
  configureBfoBuckets(config.theme?.bfo_buckets);

  graphState = readStoredState();
  for (const key of Object.keys(graphParams)) delete graphParams[key];
  Object.assign(graphParams, {
    view: graphState.view,
    ...graphState.byView[graphState.view],
  });
}

/** Point graphParams at another view's values without replacing the object. */
function applyGraphView(view) {
  graphParams.view = view;
  Object.assign(graphParams, graphState.byView[view]);
}
// Mutated in place by the panel; the simulation reads it every tick. Holds the
// active view's values, mirrored back into graphState on every change.
// The repulsion force alone could not guarantee it: it is scaled by alpha, so
// as the simulation cools the push fades and nodes settle packed.

function workerLabel(record) {
  const props = record?.properties || [];
  const worker = props.find(
    (p) => p.uri === "personnel:isActOfWorkingOf" || p.label === "worker"
  );
  return worker?.value || "";
}

function buildGraphIndex(data) {
  const peopleById = Object.fromEntries((data.people || []).map((p) => [p.id, p]));
  const processesById = Object.fromEntries((data.processes || []).map((p) => [p.id, p]));
  const entitiesById = Object.fromEntries((data.entities || []).map((e) => [e.id, e]));
  const workingHubByPerson = new Map();
  const personToProcesses = new Map();
  const relations = data.relations || [];

  for (const rel of relations) {
    if (rel.predicateLabel === "has act of working" && peopleById[rel.from]) {
      const target = entitiesById[rel.to] || processesById[rel.to];
      if (target?.isWorkingHub || isProcessRecord(target)) {
        workingHubByPerson.set(rel.from, rel.to);
        if (!personToProcesses.has(rel.from)) personToProcesses.set(rel.from, []);
        personToProcesses.get(rel.from).push(rel.to);
      }
    }
  }

  const suppressedIds = suppressOldProcesses([
    ...Object.values(entitiesById),
    ...Object.values(processesById),
  ]);

  return {
    peopleById,
    processesById,
    entitiesById,
    relations,
    suppressedIds,
    workingHubByPerson,
    personToProcesses,
  };
}

/** ISO start of a record's temporal region - the ordering key for "most recent". */
function recencyKey(record) {
  return record?.startedAt || record?.endedAt || "";
}

/** Every process occupies a temporal region, so BFO bucket alone identifies one. */
function isProcessRecord(record) {
  return record?.bfoBucket === "Process";
}

/**
 * Keep only the {@link MAX_PROCESSES_PER_CLASS} most recent processes of each
 * class and return the ids of the rest. Suppressed processes are removed from
 * the relation graph before traversal, so nothing is reached through them.
 */
function suppressOldProcesses(records, limit = MAX_PROCESSES_PER_CLASS) {
  const cap = Number.isFinite(limit) && limit > 0 ? limit : 10;
  const byPersonClass = new Map();
  for (const record of records) {
    if (!isProcessRecord(record)) continue;
    const worker = workerLabel(record);
    const classKey = record.classLabel || "Process";
    const key = worker ? `${worker}\0${classKey}` : classKey;
    const list = byPersonClass.get(key) || [];
    list.push(record);
    byPersonClass.set(key, list);
  }

  const suppressed = new Set();
  for (const list of byPersonClass.values()) {
    if (list.length <= cap) continue;
    const ordered = [...list].sort(
      (a, b) =>
        recencyKey(b).localeCompare(recencyKey(a)) || String(a.id).localeCompare(String(b.id))
    );
    for (const record of ordered.slice(cap)) suppressed.add(record.id);
  }
  return suppressed;
}

function collectVisibleGraph(adj, rootId, distance) {
  const maxDistance = Math.max(1, Math.floor(distance));
  const suppressed = adj.suppressedIds || new Set();
  const relations = (adj.relations || [])
    .filter((rel) => rel.canvas !== false)
    .filter((rel) => !suppressed.has(rel.from) && !suppressed.has(rel.to));
  const adjacency = new Map();

  for (const rel of relations) {
    const fromRelations = adjacency.get(rel.from) || [];
    fromRelations.push(rel);
    adjacency.set(rel.from, fromRelations);
    const toRelations = adjacency.get(rel.to) || [];
    toRelations.push(rel);
    adjacency.set(rel.to, toRelations);
  }

  // True graph distance: ring 1 contains every class/process directly linked
  // to the selected person, ring 2 their neighbours, and so on.
  const nodeDistance = new Map([[rootId, 0]]);
  const queue = [rootId];
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const nodeId = queue[cursor];
    const currentDistance = nodeDistance.get(nodeId);
    if (currentDistance >= maxDistance) continue;
    for (const rel of adjacency.get(nodeId) || []) {
      const neighbourId = rel.from === nodeId ? rel.to : rel.from;
      if (nodeDistance.has(neighbourId)) continue;
      nodeDistance.set(neighbourId, currentDistance + 1);
      queue.push(neighbourId);
    }
  }

  const active = new Set(nodeDistance.keys());
  const visibleRelations = relations.filter(
    (rel) => active.has(rel.from) && active.has(rel.to)
  );

  return {
    people: [...active].map((id) => adj.peopleById[id]).filter(Boolean),
    processes: [...active].map((id) => adj.processesById?.[id]).filter(Boolean),
    entities: [...active].map((id) => adj.entitiesById[id]).filter(Boolean),
    relations: visibleRelations,
  };
}

/** Act-of-working roots in a visible set (one row per process instance). */
function isProcessRoot(record) {
  return Boolean(record?.isWorkingHub || isProcessRecord(record));
}

function findProcessRecord(visible, id) {
  return (
    visible.entities?.find((record) => record.id === id) ||
    visible.processes?.find((record) => record.id === id) ||
    null
  );
}

function visibleProcessOptions(visible) {
  const byId = new Map();
  const add = (record) => {
    if (!record || !isProcessRoot(record)) return;
    const type = record.classLabel || "Process";
    byId.set(record.id, {
      id: record.id,
      label: record.label || type,
      type,
      bucket: record.bfoBucket || "Process",
    });
  };
  for (const process of visible.processes || []) add(process);
  for (const entity of visible.entities || []) add(entity);
  return [...byId.values()].sort(
    (a, b) => a.type.localeCompare(b.type) || a.label.localeCompare(b.label)
  );
}

/** Distinct process types (ontology class labels) with instance counts. */
function visibleProcessTypeOptions(instances) {
  const byType = new Map();
  for (const instance of instances) {
    const entry = byType.get(instance.type) || {
      label: instance.type,
      bucket: instance.bucket,
      count: 0,
    };
    entry.count += 1;
    byType.set(instance.type, entry);
  }
  return [...byType.values()].sort((a, b) => a.label.localeCompare(b.label));
}

/** Instances limited to process types that remain selected. */
function visibleProcessInstanceOptions(instances, hiddenProcessTypes) {
  return instances.filter((instance) => !hiddenProcessTypes.has(instance.type));
}

/**
 * Map every non-root node to the nearest act of working that reaches it.
 * The focus person is excluded from traversal so person-level edges do not
 * merge distinct process rays.
 */
function assignNodesToProcessRoots(visible, focusPersonId, { seedRootIds = null } = {}) {
  const allProcessRoots = visibleProcessOptions(visible);
  const allRootIds = new Set(allProcessRoots.map((process) => process.id));
  let processRoots = allProcessRoots;
  if (seedRootIds) {
    processRoots = allProcessRoots.filter((process) => seedRootIds.has(process.id));
  }
  if (processRoots.length === 0) return new Map();

  const adjacency = new Map();
  for (const rel of visible.relations || []) {
    if (!adjacency.has(rel.from)) adjacency.set(rel.from, new Set());
    if (!adjacency.has(rel.to)) adjacency.set(rel.to, new Set());
    adjacency.get(rel.from).add(rel.to);
    adjacency.get(rel.to).add(rel.from);
  }

  const assignments = new Map();
  const queue = [];
  for (const root of processRoots) {
    assignments.set(root.id, root.id);
    queue.push(root.id);
  }

  for (let cursor = 0; cursor < queue.length; cursor++) {
    const nodeId = queue[cursor];
    const rootId = assignments.get(nodeId);
    for (const neighbour of adjacency.get(nodeId) || []) {
      if (neighbour === focusPersonId || allRootIds.has(neighbour)) continue;
      if (!assignments.has(neighbour)) {
        assignments.set(neighbour, rootId);
        queue.push(neighbour);
      }
    }
  }

  return assignments;
}

/**
 * Drop deselected acts of working and every node reached only through them.
 * The focus person and nodes attached directly to the person stay visible.
 */
function applyProcessFilter(
  visible,
  hiddenProcessIds,
  hiddenProcessTypes,
  focusPersonId,
  { strict = false, seedRootIds = null } = {}
) {
  const allProcesses = visibleProcessOptions(visible);
  const hiddenTypes = hiddenProcessTypes || new Set();
  const hiddenIds = hiddenProcessIds || new Set();
  const effectivelyHidden = new Set(hiddenIds);
  for (const process of allProcesses) {
    if (hiddenTypes.has(process.type)) effectivelyHidden.add(process.id);
  }
  if (effectivelyHidden.size === 0) return visible;

  const rootIds = new Set(allProcesses.map((process) => process.id));
  const visibleRootIds =
    seedRootIds ||
    new Set(allProcesses.filter((process) => !effectivelyHidden.has(process.id)).map((p) => p.id));
  const assignments = assignNodesToProcessRoots(visible, focusPersonId, {
    seedRootIds: strict ? visibleRootIds : null,
  });

  const keepNode = (record) => {
    if (!record) return false;
    if (record.id === focusPersonId) return true;
    if (rootIds.has(record.id)) return !effectivelyHidden.has(record.id);
    const rootId = assignments.get(record.id);
    if (!rootId) return !strict;
    return !effectivelyHidden.has(rootId);
  };

  const people = (visible.people || []).filter(keepNode);
  const entities = (visible.entities || []).filter(keepNode);
  const processes = (visible.processes || []).filter(keepNode);
  const liveIds = new Set(
    [...people, ...entities, ...processes].map((record) => record.id)
  );

  return {
    people,
    entities,
    processes,
    relations: (visible.relations || []).filter(
      (rel) => liveIds.has(rel.from) && liveIds.has(rel.to)
    ),
  };
}

function classLabelOf(record) {
  if (record?.nodeKind === "person" || record?.kind === "employee") return "Person";
  return record?.classLabel || "Unknown";
}

/** Non-process nodes that the class filter can toggle (processes have their own filters). */
function visibleClassInstanceOptions(visible, focusPersonId) {
  const byId = new Map();
  const add = (record) => {
    if (!record || isProcessRoot(record) || record.id === focusPersonId) return;
    const type = classLabelOf(record);
    byId.set(record.id, {
      id: record.id,
      label: record.label || type,
      type,
      bucket: record.bfoBucket || (type === "Person" ? "Material Entity" : "Unknown"),
    });
  };
  for (const person of visible.people || []) add(person);
  for (const entity of visible.entities || []) add(entity);
  for (const process of visible.processes || []) add(process);
  return [...byId.values()].sort(
    (a, b) => a.type.localeCompare(b.type) || a.label.localeCompare(b.label)
  );
}

/** Distinct class types with instance counts, excluding process nodes. */
function visibleClassTypeOptions(instances) {
  const byType = new Map();
  for (const instance of instances) {
    const entry = byType.get(instance.type) || {
      label: instance.type,
      bucket: instance.bucket,
      count: 0,
    };
    entry.count += 1;
    byType.set(instance.type, entry);
  }
  return [...byType.values()].sort((a, b) => a.label.localeCompare(b.label));
}

/** Class instances limited to types that remain selected. */
function visibleClassInstanceOptionsForTypes(instances, hiddenClassTypes) {
  return instances.filter((instance) => !hiddenClassTypes.has(instance.type));
}

/**
 * Drop deselected class types or instances. Process nodes are untouched here -
 * they are controlled by the process filters above.
 */
function applyClassFilter(visible, hiddenClassInstances, hiddenClassTypes, focusPersonId) {
  const allInstances = visibleClassInstanceOptions(visible, focusPersonId);
  const hiddenTypes = hiddenClassTypes || new Set();
  const hiddenIds = hiddenClassInstances || new Set();
  const effectivelyHidden = new Set(hiddenIds);
  for (const instance of allInstances) {
    if (hiddenTypes.has(instance.type)) effectivelyHidden.add(instance.id);
  }
  if (effectivelyHidden.size === 0) return visible;

  const keepNode = (record) => {
    if (!record) return false;
    if (record.id === focusPersonId) return true;
    if (isProcessRoot(record)) return true;
    return !effectivelyHidden.has(record.id);
  };

  const people = (visible.people || []).filter(keepNode);
  const entities = (visible.entities || []).filter(keepNode);
  const processes = (visible.processes || []).filter(keepNode);
  const liveIds = new Set(
    [...people, ...entities, ...processes].map((record) => record.id)
  );
  return {
    people,
    entities,
    processes,
    relations: (visible.relations || []).filter(
      (rel) => liveIds.has(rel.from) && liveIds.has(rel.to)
    ),
  };
}

function renderPropertiesTable(properties) {
  // Property and label share a cell, stacked. As separate columns they left
  // the narrow inspector too little room and broke URIs mid-token.
  const rows = (properties || [])
    .map(
      (p) => `<tr>
        <td class="graph-prop-name">
          <span class="graph-prop-uri">${esc(p.uri || "-")}</span>
          <span class="graph-prop-label">${esc(p.label || "-")}</span>
        </td>
        <td>${esc(p.value)}</td>
      </tr>`
    )
    .join("");
  if (!rows) return `<p class="empty">No data properties on this node.</p>`;
  return `<table class="graph-props"><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderBfoBadge(bucketType) {
  const def = bfoColor(bucketType);
  return `<span class="graph-bfo-badge" style="--bfo-color:${def.color};--bfo-border:${def.border}">${esc(def.label)}</span>`;
}

function renderNodeUri(id) {
  return `<dt>URI</dt><dd class="graph-node-uri">${esc(id || "-")}</dd>`;
}

function renderNodeDetail(node, { focusPersonId } = {}) {
  if (!node) return `<h2>Selection</h2><p class="empty">Select a node on the canvas.</p>`;
  if (node.kind === "person") {
    const person = node.person;
    return `<h2>${esc(person.label)}${node.isFocus ? " · focus" : ""}</h2>
      <dl>${renderNodeUri(person.id)}<dt>Class</dt><dd>Person</dd><dt>BFO bucket</dt><dd>${renderBfoBadge("Material Entity")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(person.properties)}`;
  }
  if (node.kind === "entity") {
    const entity = node.entity;
    return `<h2>${esc(entity.label)}</h2>
      <dl>${renderNodeUri(entity.id)}<dt>Class</dt><dd>${esc(entity.classLabel)}</dd><dt>BFO bucket</dt><dd>${renderBfoBadge(entity.bfoBucket)}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(entity.properties)}`;
  }
  if (node.kind === "process") {
    const process = node.process;
    return `<h2>${esc(process.classLabel || "Process")}</h2>
      <dl>${renderNodeUri(process.id)}<dt>BFO bucket</dt><dd>${renderBfoBadge(process.bfoBucket || "Process")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(process.properties)}`;
  }
  if (node.kind === "source") {
    const source = node.source;
    return `<h2>${esc(source.classLabel || "Source")}</h2>
      <dl>${renderNodeUri(source.id)}<dt>BFO bucket</dt><dd>${renderBfoBadge(source.bfoBucket || "Process")}</dd></dl>
      <h3>Data properties</h3>${renderPropertiesTable(source.properties)}`;
  }
  return renderNodeDetail(null);
}

function nodePalette(entity, { faded = false } = {}) {
  const bucket = entity.bfoBucket || (entity.nodeKind === "person" ? "Material Entity" : "Process");
  return bfoColor(bucket, { faded });
}

function resolveNode(id, lookup) {
  if (lookup.peopleById[id]) {
    const person = lookup.peopleById[id];
    return { id: `person:${person.id}`, kind: "person", person, label: person.label, palette: nodePalette(person) };
  }
  const process = lookup.processesById[id];
  if (process) {
    return {
      id: process.id,
      kind: "process",
      process,
      label: process.classLabel || "Process",
      palette: nodePalette(process, { faded: true }),
      dashed: true,
    };
  }
  if (lookup.entitiesById[id]) {
    const entity = lookup.entitiesById[id];
    return {
      id: entity.id,
      kind: "entity",
      entity,
      label: entity.label,
      palette: nodePalette(entity),
      isWorkingHub: entity.isWorkingHub,
    };
  }
  return null;
}

function graphNodeRadius(_n) {
  return GRAPH_NODE_RADIUS;
}

function truncateLine(line, maxChars, forceEllipsis = false) {
  if (!forceEllipsis && line.length <= maxChars) return line;
  if (maxChars <= 1) return "…";
  if (forceEllipsis && line.length < maxChars) return `${line}…`;
  return `${line.slice(0, maxChars - 1)}…`;
}

function hardBreakToken(token, maxChars) {
  if (token.length <= maxChars) return [token];
  const chunks = [];
  let rest = token;
  while (rest.length > maxChars) {
    chunks.push(rest.slice(0, maxChars));
    rest = rest.slice(maxChars);
  }
  if (rest) chunks.push(rest);
  return chunks;
}

function wrapWordLabel(label, maxCharsPerLine, maxLines) {
  const words = label.split(" ");
  const lines = [];
  let current = "";
  let wordIndex = 0;

  const pushCurrent = () => {
    if (!current) return;
    lines.push(truncateLine(current, maxCharsPerLine));
    current = "";
  };

  while (wordIndex < words.length && lines.length < maxLines) {
    const word = words[wordIndex];
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxCharsPerLine) {
      current = candidate;
      wordIndex += 1;
      continue;
    }

    pushCurrent();
    if (lines.length >= maxLines) break;

    if (word.length <= maxCharsPerLine) {
      current = word;
      wordIndex += 1;
      continue;
    }

    let rest = word;
    while (rest.length > 0 && lines.length < maxLines) {
      if (rest.length <= maxCharsPerLine) {
        current = rest;
        rest = "";
        break;
      }
      lines.push(truncateLine(rest.slice(0, maxCharsPerLine), maxCharsPerLine));
      rest = rest.slice(maxCharsPerLine);
    }
    wordIndex += 1;
  }

  if (lines.length < maxLines && current) {
    lines.push(truncateLine(current, maxCharsPerLine));
    current = "";
  }

  const truncated = wordIndex < words.length || Boolean(current);
  const result = lines.slice(0, maxLines);
  if (truncated && result.length > 0) {
    const last = result[result.length - 1];
    result[result.length - 1] = truncateLine(last, maxCharsPerLine, true);
  }
  return result;
}

function wrapNodeLabelLines(label, maxCharsPerLine, maxLines) {
  const normalized = (label || "").trim().replace(/\s+/g, " ");
  if (!normalized) return [""];
  if (normalized.length <= maxCharsPerLine && maxLines >= 1) {
    return [truncateLine(normalized, maxCharsPerLine)];
  }
  const lines = wrapWordLabel(normalized, maxCharsPerLine, maxLines);
  if (lines.length > 0) return lines;
  return [truncateLine(normalized, maxCharsPerLine)];
}

function nodeLabelLayout(n) {
  const maxWidth = GRAPH_NODE_RADIUS * 1.75;
  const maxCharsPerLine = Math.max(4, Math.floor(maxWidth / (NODE_LABEL_FONT_SIZE * 0.52)));
  const maxLines = Math.max(1, Math.floor((GRAPH_NODE_RADIUS * 1.55) / NODE_LABEL_LINE_HEIGHT));
  return {
    fontSize: NODE_LABEL_FONT_SIZE,
    lineHeight: NODE_LABEL_LINE_HEIGHT,
    lines: wrapNodeLabelLines(n.label, maxCharsPerLine, maxLines),
  };
}

function graphNodeExtent(_n) {
  const pad = 6;
  return { rx: GRAPH_NODE_RADIUS + pad, ry: GRAPH_NODE_RADIUS + pad };
}

function resolveOverlaps(
  nodes,
  { iterations = 120, pinnedIds = new Set(), minGap = 10 } = {}
) {
  for (let iter = 0; iter < iterations; iter++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const aPinned = a.pinned || pinnedIds.has(a.id);
        const bPinned = b.pinned || pinnedIds.has(b.id);
        if (aPinned && bPinned) continue;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const ea = graphNodeExtent(a);
        const eb = graphNodeExtent(b);
        const need = ea.rx + eb.rx + minGap;
        const overlap = need - dist;
        if (overlap <= 0) continue;
        const push = overlap * 0.55 + 0.5;
        if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) {
          dx = (j - i) * 0.37;
          dy = 1;
        }
        const nx = dx / dist;
        const ny = dy / dist;
        if (!aPinned) {
          a.x -= nx * push * (bPinned ? 1 : 0.5);
          a.y -= ny * push * (bPinned ? 1 : 0.5);
          moved = true;
        }
        if (!bPinned) {
          b.x += nx * push * (aPinned ? 1 : 0.5);
          b.y += ny * push * (aPinned ? 1 : 0.5);
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
}

function seedSemanticLayout(focusNode, workingNode, nodes, edges, focusPersonId) {
  focusNode.x = 0;
  focusNode.y = 0;
  focusNode.z = 0;
  const processRoots = nodes
    .filter(
      (node) =>
        node.id !== focusNode.id &&
        (node.isWorkingHub || node.kind === "process")
    )
    .sort((a, b) => {
      const priority = (node) => {
        if (node.id === workingNode?.id) return 0;
        if (node.isWorkingHub) return 1;
        return 2;
      };
      return priority(a) - priority(b) || a.label.localeCompare(b.label) || a.id.localeCompare(b.id);
    });

  if (processRoots.length === 0) {
    const others = nodes.filter((node) => node.id !== focusNode.id);
    others.forEach((node, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(1, others.length);
      const radius = 170 + Math.floor(index / 8) * 170;
      node.x = Math.cos(angle) * radius;
      node.y = Math.sin(angle) * radius;
      node.z = Math.sin(index * 2.399963) * radius * 0.6;
      node.rayId = null;
      node.radialLevel = Math.floor(index / 8) + 1;
    });
    for (const node of nodes) {
      node.homeX = node.x;
      node.homeY = node.y;
      node.physicsEnabled = node.id !== focusNode.id;
    }
    return;
  }

  const rootIds = new Set(processRoots.map((node) => node.id));
  const rootRank = new Map(processRoots.map((node, index) => [node.id, index]));
  const adjacency = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if (edge.hidden) continue;
    adjacency.get(edge.a.id)?.push(edge.b);
    adjacency.get(edge.b.id)?.push(edge.a);
  }
  for (const neighbours of adjacency.values()) {
    neighbours.sort((a, b) => a.id.localeCompare(b.id));
  }

  // Assign every class to its nearest process without traversing through the
  // centered person, which would otherwise merge otherwise distinct rays.
  const assignments = new Map();
  const queue = [];
  for (const root of processRoots) {
    assignments.set(root.id, { rootId: root.id, hop: 0 });
    queue.push(root);
  }
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const node = queue[cursor];
    const current = assignments.get(node.id);
    for (const neighbour of adjacency.get(node.id) || []) {
      if (neighbour.id === focusNode.id || rootIds.has(neighbour.id)) continue;
      const candidate = { rootId: current.rootId, hop: current.hop + 1 };
      const existing = assignments.get(neighbour.id);
      const candidateRank = rootRank.get(candidate.rootId);
      const existingRank = existing ? rootRank.get(existing.rootId) : Infinity;
      if (
        !existing ||
        candidate.hop < existing.hop ||
        (candidate.hop === existing.hop && candidateRank < existingRank)
      ) {
        assignments.set(neighbour.id, candidate);
        queue.push(neighbour);
      }
    }
  }

  // Source-only or disconnected nodes still receive a stable ray.
  const unassigned = nodes
    .filter((node) => node.id !== focusNode.id && !assignments.has(node.id))
    .sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  unassigned.forEach((node, index) => {
    const root = processRoots[index % processRoots.length];
    assignments.set(node.id, { rootId: root.id, hop: 1 });
  });

  const clustered = graphParams.clusterBy !== "none" && graphParams.clusterPull > 0;
  // A cluster occupies a disc around its process, so the processes themselves
  // have to sit far enough apart for those discs not to overlap.
  const clusterRadius = GRAPH_NODE_RADIUS + graphParams.nodeMinGap;
  const minimumRootSpacing = clustered
    ? clusterRadius * 4.4
    : GRAPH_NODE_RADIUS * 2 + 48;
  const rootRadius =
    processRoots.length === 1
      ? PROCESS_ROOT_RADIUS
      : Math.max(
          clustered ? minimumRootSpacing : PROCESS_ROOT_RADIUS,
          minimumRootSpacing / (2 * Math.sin(Math.PI / processRoots.length))
        );
  const ringGap = 180;
  const sectorSize = (Math.PI * 2) / processRoots.length;
  const sectorSpan =
    processRoots.length === 1 ? Math.PI * 1.5 : Math.min(Math.PI * 0.8, sectorSize * 0.72);

  const bucketOrder = [
    "Site",
    "Temporal Region",
    "Quality",
    "Realizable",
    "GDC",
    "Material Entity",
    "Process",
  ];
  const bucketRank = (node) => {
    const bucket =
      node.entity?.bfoBucket || node.person?.bfoBucket || node.process?.bfoBucket || "";
    const index = bucketOrder.indexOf(bucket);
    return index === -1 ? bucketOrder.length : index;
  };

  processRoots.forEach((root, rayIndex) => {
    const rayAngle = rayIndex * sectorSize;
    root.x = Math.cos(rayAngle) * rootRadius;
    root.y = Math.sin(rayAngle) * rootRadius;
    root.rayId = root.id;
    root.radialLevel = 1;
    root.isProcessAnchor = true;
    // Depth is fixed per cluster: the golden angle spreads the processes
    // through the z range without any two landing on the same plane.
    const rootZ = Math.sin(rayIndex * 2.399963) * (rootRadius * 0.85);
    root.z = rootZ;

    const members = nodes
      .filter(
        (node) =>
          node.id !== focusNode.id &&
          node.id !== root.id &&
          assignments.get(node.id)?.rootId === root.id
      )
      .sort((a, b) => {
        const assignmentA = assignments.get(a.id);
        const assignmentB = assignments.get(b.id);
        return (
          assignmentA.hop - assignmentB.hop ||
          bucketRank(a) - bucketRank(b) ||
          a.label.localeCompare(b.label) ||
          a.id.localeCompare(b.id)
        );
      });

    const levels = new Map();
    for (const node of members) {
      const minimumLevel = Math.max(2, assignments.get(node.id).hop + 1);
      let level = minimumLevel;
      while ((levels.get(level)?.length || 0) >= 2 ** (level - 1)) level += 1;
      const levelNodes = levels.get(level) || [];
      levelNodes.push(node);
      levels.set(level, levelNodes);
    }

    for (const [level, levelNodes] of levels.entries()) {
      levelNodes.forEach((node, index) => {
        // Declared out here because the depth below needs it too; each branch
        // scoped its own copy, which is what broke the 3D view.
        let angle;
        if (clustered) {
          // Orbit the process: a compact group centred on its own act.
          const ringRadius = clusterRadius * level * 0.95;
          angle =
            rayAngle +
            Math.PI +
            (Math.PI * 2 * index) / Math.max(1, levelNodes.length) +
            level * 0.6;
          node.x = root.x + Math.cos(angle) * ringRadius;
          node.y = root.y + Math.sin(angle) * ringRadius;
        } else {
          const radius = rootRadius + (level - 1) * ringGap;
          const offset =
            levelNodes.length === 1
              ? 0
              : -sectorSpan / 2 + (sectorSpan * index) / (levelNodes.length - 1);
          angle = rayAngle + offset;
          node.x = Math.cos(angle) * radius;
          node.y = Math.sin(angle) * radius;
        }
        node.rayId = root.id;
        node.radialLevel = level;
        // Members sit around their process in depth as well as in plane.
        node.z = rootZ + Math.cos(angle + level) * (clusterRadius * 0.6);
      });
    }
  });

  resolveOverlaps(nodes, {
    iterations: Math.max(120, nodes.length * 6),
    pinnedIds: new Set([focusNode.id].filter(Boolean)),
    minGap: graphParams.nodeMinGap,
  });
  for (const node of nodes) {
    node.homeX = node.x;
    node.homeY = node.y;
    // Everything but the focus is simulated - the focus stays put so the
    // canvas keeps a stable centre to fit and pan around.
    node.physicsEnabled = node.id !== focusNode.id;
  }
}

function directedEdgeKey(fromId, toId) {
  return `${fromId}\x00${toId}`;
}

function canonicalPairKey(idA, idB) {
  return idA < idB ? `${idA}\x00${idB}` : `${idB}\x00${idA}`;
}

function splitCanonicalPair(key) {
  const sep = key.indexOf("\0");
  return [key.slice(0, sep), key.slice(sep + 1)];
}

/** Roundness values for parallel edges between the same node pair (max 0.6). Ported from Nexus vis-network. */
function computeParallelEdgeRoundness(count) {
  if (count <= 0) return [];
  if (count === 1) return [0];
  if (count === 2) return [0.28, -0.28];

  const pairCount = Math.floor(count / 2);
  const hasCenter = count % 2 === 1;
  const tierOffset = hasCenter ? 1 : 0;
  const baseRoundness = 0.18;
  const roundnessStep = 0.12;
  const maxRoundness = 0.6;

  const values = [];
  for (let tier = 1; tier <= pairCount; tier++) {
    const r = Math.min(maxRoundness, baseRoundness + (tier + tierOffset - 1) * roundnessStep);
    values.push(r, -r);
  }
  if (hasCenter) {
    values.splice(Math.floor(values.length / 2), 0, 0);
  }
  return values;
}

/** Assign non-overlapping curved/straight routing per edge within each undirected node pair. */
function annotateEdgeCurves(edges) {
  const groups = new Map();
  let idx = 0;

  for (const edge of edges) {
    if (edge.hidden) {
      edge.curveConfig = { enabled: false };
      continue;
    }
    edge.edgeId =
      edge.edgeId || `${edge.a.id}\0${edge.b.id}\0${edge.predicateLabel || ""}\0${idx++}`;
    const key = canonicalPairKey(edge.a.id, edge.b.id);
    const list = groups.get(key) ?? [];
    list.push(edge);
    groups.set(key, list);
  }

  for (const [key, group] of groups.entries()) {
    if (group.length <= 1) {
      if (group.length === 1) group[0].curveConfig = { enabled: false };
      continue;
    }

    const sorted = [...group].sort((a, b) => a.edgeId.localeCompare(b.edgeId));
    const roundnesses = computeParallelEdgeRoundness(sorted.length);
    const [canonicalA, canonicalB] = splitCanonicalPair(key);

    const forward = sorted.filter((e) => e.a.id === canonicalA && e.b.id === canonicalB);
    const reverse = sorted.filter((e) => e.a.id === canonicalB && e.b.id === canonicalA);

    if (forward.length > 0 && reverse.length > 0) {
      // Bidirectional inverses: same curve direction so mirrored routes do not overlap.
      let roundIdx = 0;
      for (const edge of [...forward, ...reverse]) {
        const magnitude = Math.abs(roundnesses[roundIdx] ?? roundnesses.at(-1) ?? 0.1) || 0.1;
        edge.curveConfig = { enabled: true, type: "curvedCW", roundness: magnitude };
        roundIdx += 1;
      }
      continue;
    }

    sorted.forEach((edge, i) => {
      const magnitude = Math.abs(roundnesses[i] ?? 0);
      if (magnitude === 0) {
        edge.curveConfig = { enabled: false };
        return;
      }
      edge.curveConfig = {
        enabled: true,
        type: i % 2 === 0 ? "curvedCW" : "curvedCCW",
        roundness: magnitude,
      };
    });
  }
}

let CAMERA_DISTANCE;

/** Screen-space X of a node: the projection in 3D, the raw position in 2D. */
function viewX(node) {
  return node._px ?? node.x;
}

function viewY(node) {
  return node._py ?? node.y;
}

/** Perspective scale at a node's depth. 1 in 2D, and in front-to-back order. */
function viewScale(node) {
  return node._ds ?? 1;
}

/**
 * Rotate every node about the vertical then horizontal axis and project.
 * The simulation stays two-dimensional; z is fixed per cluster at seed time,
 * so orbiting reveals the grouping as depth rather than re-running any physics.
 */
function projectNodes(nodes, yaw, pitch) {
  if (graphParams.view !== "3d") {
    for (const node of nodes) {
      node._px = undefined;
      node._py = undefined;
      node._ds = 1;
      node._depth = 0;
    }
    return;
  }
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  for (const node of nodes) {
    const z = node.z || 0;
    const x1 = node.x * cosYaw + z * sinYaw;
    const z1 = -node.x * sinYaw + z * cosYaw;
    const y1 = node.y * cosPitch - z1 * sinPitch;
    const z2 = node.y * sinPitch + z1 * cosPitch;
    // Clamped so a node level with the camera cannot blow the scale up.
    const k = CAMERA_DISTANCE / Math.max(400, CAMERA_DISTANCE + z2);
    node._px = x1 * k;
    node._py = y1 * k;
    node._ds = k;
    node._depth = z2;
  }
}

function nodeBoundaryPoint(from, to, radius) {
  const dx = viewX(to) - viewX(from);
  const dy = viewY(to) - viewY(from);
  const dist = Math.hypot(dx, dy) || 1;
  return {
    x: viewX(from) + (dx / dist) * radius,
    y: viewY(from) + (dy / dist) * radius,
  };
}

function pointOnQuadratic(t, start, control, end) {
  const u = 1 - t;
  return {
    x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
    y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
  };
}

function tangentOnQuadratic(t, start, control, end) {
  const u = 1 - t;
  return {
    x: 2 * u * (control.x - start.x) + 2 * t * (end.x - control.x),
    y: 2 * u * (control.y - start.y) + 2 * t * (end.y - control.y),
  };
}

function edgeGeometry(edge) {
  const startRadius = graphNodeRadius(edge.a) * viewScale(edge.a) + 4;
  const endRadius = graphNodeRadius(edge.b) * viewScale(edge.b) + 4;
  const start = nodeBoundaryPoint(edge.a, edge.b, startRadius);
  const end = nodeBoundaryPoint(edge.b, edge.a, endRadius);
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const len = Math.hypot(dx, dy) || 1;
  const normalX = -dy / len;
  const normalY = dx / len;
  const cfg = edge.curveConfig || { enabled: false };
  if (!cfg.enabled || !cfg.roundness) {
    return { start, end, control: { x: midX, y: midY }, curved: false };
  }
  const sign = cfg.type === "curvedCCW" ? -1 : 1;
  const offset = cfg.roundness * len;
  return {
    start,
    end,
    control: { x: midX + normalX * offset * sign, y: midY + normalY * offset * sign },
    curved: true,
  };
}

/**
 * Group a node belongs to. `rayId` is assigned by the seeding pass, which
 * already walks every class back to its nearest process, so clustering by act
 * of working needs no traversal of its own.
 */
function clusterKeyOf(node) {
  if (graphParams.clusterBy === "process") return node.rayId || node.id;
  if (graphParams.clusterBy === "bucket") {
    return node.entity?.bfoBucket || node.person?.bfoBucket || node.kind;
  }
  return null;
}

function classPhysicsStep(nodes, edges, alpha) {
  for (const node of nodes) {
    node.vx = (node.vx || 0) * 0.68;
    node.vy = (node.vy || 0) * 0.68;
  }

  if (!edges.degreesCounted) {
    const degree = new Map();
    for (const edge of edges) {
      if (edge.hidden) continue;
      degree.set(edge.a.id, (degree.get(edge.a.id) || 0) + 1);
      degree.set(edge.b.id, (degree.get(edge.b.id) || 0) + 1);
    }
    for (const edge of edges) {
      edge.linkWeight =
        1 / Math.max(1, Math.min(degree.get(edge.a.id) || 1, degree.get(edge.b.id) || 1));
    }
    edges.degreesCounted = true;
  }

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      if (!a.physicsEnabled && !b.physicsEnabled) continue;

      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let distance = Math.hypot(dx, dy);
      if (distance < 0.01) {
        dx = (j - i) * 0.37;
        dy = 1;
        distance = Math.hypot(dx, dy);
      }

      const minimumDistance = GRAPH_NODE_RADIUS * 2 + 54;
      let strength = (alpha * graphParams.repulsion) / (distance * distance);
      if (distance < minimumDistance) {
        strength += ((minimumDistance - distance) / minimumDistance) * 1.2 * alpha;
      }
      const forceX = (dx / distance) * strength;
      const forceY = (dy / distance) * strength;
      if (a.physicsEnabled) {
        a.vx -= forceX;
        a.vy -= forceY;
      }
      if (b.physicsEnabled) {
        b.vx += forceX;
        b.vy += forceY;
      }
    }
  }

  for (const edge of edges) {
    if (edge.hidden) continue;
    const a = edge.a;
    const b = edge.b;
    if (!a.physicsEnabled && !b.physicsEnabled) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const distance = Math.hypot(dx, dy) || 0.01;
    if (!Number.isFinite(edge.physicsLength)) {
      // A uniform target length. Freezing the seeded distance here made every
      // edge start at rest, so the simulation had no work to do and the seed
      // was the layout - which is why nothing ever appeared to move.
      edge.physicsLength = graphParams.linkDistance;
    }
    const strength =
      (distance - edge.physicsLength) * 0.5 * (edge.linkWeight ?? 1) * alpha;
    const forceX = (dx / distance) * strength;
    const forceY = (dy / distance) * strength;
    if (a.physicsEnabled) {
      a.vx += forceX;
      a.vy += forceY;
    }
    if (b.physicsEnabled) {
      b.vx -= forceX;
      b.vy -= forceY;
    }
  }

  // Clustering anchors each group to where the seeding pass put it. The seed
  // already fans the acts of working out into separate angular sectors, so the
  // groups start well apart; emergent forces alone could not reproduce that,
  // because all-pairs repulsion cancels a pull toward a live centroid and the
  // groups end up evenly mixed. Pulling toward the group's *seeded* centre
  // instead keeps the sectors intact while the simulation still handles
  // spacing inside each one.
  if (graphParams.clusterBy !== "none" && graphParams.clusterPull > 0) {
    const groups = new Map();
    for (const node of nodes) {
      const key = clusterKeyOf(node);
      if (!key) continue;
      const entry = groups.get(key) || { x: 0, y: 0, count: 0 };
      entry.x += node.homeX ?? node.x;
      entry.y += node.homeY ?? node.y;
      entry.count += 1;
      groups.set(key, entry);
    }

    const pull = (graphParams.clusterPull / 100) * 0.05;
    for (const node of nodes) {
      if (!node.physicsEnabled) continue;
      const entry = groups.get(clusterKeyOf(node));
      // A group of one has no centre to be drawn toward.
      if (!entry || entry.count < 2) continue;
      node.vx += (entry.x / entry.count - node.x) * pull * alpha;
      node.vy += (entry.y / entry.count - node.y) * pull * alpha;
    }
  }

  for (const node of nodes) {
    if (!node.physicsEnabled) {
      node.x = node.homeX;
      node.y = node.homeY;
      node.vx = 0;
      node.vy = 0;
      continue;
    }

    // No tether: the seeded ray is a starting point only, and the link and
    // repulsion forces decide where every node ends up.
    const speed = Math.hypot(node.vx, node.vy);
    if (speed > 10) {
      node.vx = (node.vx / speed) * 10;
      node.vy = (node.vy / speed) * 10;
    }
    node.x += node.vx;
    node.y += node.vy;
  }

  resolveOverlaps(nodes, { iterations: 2, minGap: graphParams.nodeMinGap });
}

function settleClassPhysicsSync(nodes, edges, focusNode, { steps = 90 } = {}) {
  for (let step = 0; step < steps; step++) {
    const alpha = Math.max(0.04, 1 - step / steps);
    classPhysicsStep(nodes, edges, alpha);
  }
  resolveOverlaps(nodes, {
    iterations: Math.max(80, nodes.length * 4),
    pinnedIds: new Set([focusNode.id].filter(Boolean)),
  });
}

function runClassPhysics(
  nodes,
  edges,
  focusNode,
  { onTick, onEnd, maxMs = graphParams.settleMs } = {}
) {
  const started = performance.now();
  let rafId = 0;

  const stop = (complete = false) => {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = 0;
    if (complete) {
      settleClassPhysicsSync(nodes, edges, focusNode, { steps: 24 });
      onEnd?.();
    }
  };

  const tick = () => {
    const elapsed = performance.now() - started;
    if (elapsed >= maxMs) {
      stop(true);
      return;
    }
    const alpha = Math.max(0.04, 1 - elapsed / maxMs);
    classPhysicsStep(nodes, edges, alpha);
    onTick?.();
    rafId = requestAnimationFrame(tick);
  };

  rafId = requestAnimationFrame(tick);
  return () => stop(false);
}

function buildGraph(focusPerson, visible, lookup) {
  const nodeMap = new Map();
  const addNode = (id, extra = {}) => {
    const base = resolveNode(id, lookup);
    if (!base || nodeMap.has(base.id)) return nodeMap.get(base.id);
    const node = { ...base, x: 0, y: 0, ...extra };
    nodeMap.set(node.id, node);
    return node;
  };

  const workingId =
    lookup.workingHubByPerson?.get?.(focusPerson.id) ||
    visible.entities.find((e) => e.isWorkingHub)?.id;
  const workingNode = workingId ? addNode(workingId, { isWorkingHub: true }) : null;
  const focusNode = addNode(focusPerson.id, { isFocus: true, pinned: true });

  for (const proc of visible.processes) addNode(proc.id);

  const edges = [];
  for (const rel of visible.relations) {
    const a = addNode(rel.from);
    const b = addNode(rel.to);
    if (!a || !b) continue;
    edges.push({ a, b, predicateLabel: rel.predicateLabel, hidden: rel.canvas === false });
  }

  annotateEdgeCurves(edges);

  const nodes = [...nodeMap.values()];
  focusNode.x = 0;
  focusNode.y = 0;

  return { nodes, edges, focusNode, workingNode };
}

export function layoutGraphNodes(focusPerson, visible, lookup) {
  const graph = buildGraph(focusPerson, visible, lookup);
  seedSemanticLayout(
    graph.focusNode,
    graph.workingNode,
    graph.nodes,
    graph.edges,
    focusPerson.id
  );
  return graph;
}

function countOverlaps(nodes) {
  let n = 0;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i];
      const b = nodes[j];
      const ea = graphNodeExtent(a);
      const eb = graphNodeExtent(b);
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      if (dist < ea.rx + eb.rx) n += 1;
    }
  }
  return n;
}

export {
  GRAPH_NODE_RADIUS,
  PROCESS_ROOT_RADIUS,
  graphNodeExtent,
  countOverlaps,
  MAX_PROCESSES_PER_CLASS,
  buildGraphIndex,
  collectVisibleGraph,
  visibleProcessOptions,
  visibleProcessTypeOptions,
  visibleProcessInstanceOptions,
  assignNodesToProcessRoots,
  applyProcessFilter,
  visibleClassInstanceOptions,
  visibleClassTypeOptions,
  visibleClassInstanceOptionsForTypes,
  applyClassFilter,
  suppressOldProcesses,
  resolveNode,
  resolveOverlaps,
  seedSemanticLayout,
  settleClassPhysicsSync,
  computeParallelEdgeRoundness,
  annotateEdgeCurves,
  nodeLabelLayout,
  wrapNodeLabelLines,
};

/**
 * Open at 1:1 on the focus node. Fitting the whole graph in shrank it until the
 * relations between nodes were unreadable; at a standard zoom the labels are
 * legible and the canvas is pannable to reach the rest.
 */
function resetGraphView(canvas, focusNode, setPanScale) {
  const scale = graphParams.zoom;
  setPanScale({
    scale,
    panX: -(focusNode?.x ?? 0) * scale,
    panY: -(focusNode?.y ?? 0) * scale,
  });
}

function mountGraphCanvas(root, options) {
  const { focusPerson, visible, lookup } = options;
  const stage = root.querySelector("#graph-stage");
  const canvas = root.querySelector("#graph-canvas");
  const detail = root.querySelector("#graph-detail");
  const ctx = canvas.getContext("2d");
  const style = getComputedStyle(document.documentElement);
  const panel = style.getPropertyValue("--panel").trim();
  const colors = {
    ink: style.getPropertyValue("--ink").trim(),
    muted: style.getPropertyValue("--muted").trim(),
    nodeFill: style.getPropertyValue("--graph-node-fill").trim(),
    nodeFillMuted: style.getPropertyValue("--graph-node-fill-muted").trim(),
    panel,
    canvas: panel,
  };

  const { nodes, edges, focusNode } = layoutGraphNodes(focusPerson, visible, {
    ...lookup,
    workingHubByPerson: options.workingHubByPerson,
  });
  let selected = focusNode;
  let pan = { x: 0, y: 0 };
  let scale = 1;
  let dragging = null;
  let panning = null;
  let offset = { x: 0, y: 0 };
  let pointerStart = null;
  let recentring = null;
  const layoutDone = true;
  let stopPhysics = null;
  // Camera orientation for the 3D view. Ignored entirely in 2D.
  const orbit = { yaw: -0.6, pitch: 0.35 };
  let orbiting = null;

  function setPanScale({ scale: s, panX, panY }) {
    scale = s;
    pan.x = panX;
    pan.y = panY;
  }

  const body = root.querySelector(".graph-body");

  function renderDetail(node) {
    if (!detail) return;
    const close =
      '<button type="button" class="graph-detail-close" id="graph-detail-close" title="Close inspector" aria-label="Close inspector">×</button>';
    const content = node
      ? renderNodeDetail(node, { focusPersonId: focusPerson.id })
      : renderNodeDetail(null);
    detail.innerHTML = `${close}<p class="graph-inspect-kicker">Inspect</p>${content}`;
    detail
      .querySelector("#graph-detail-close")
      ?.addEventListener("click", closeDetail);
  }

  /** Opening and closing changes the stage width, so the canvas is resized. */
  function setDetailOpen(open) {
    if (!body) return;
    body.classList.toggle("detail-open", open);
    resize();
  }

  function closeDetail() {
    setDetailOpen(false);
  }

  function showDetail(node) {
    renderDetail(node);
    setDetailOpen(true);
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(stage.clientWidth * dpr);
    canvas.height = Math.floor(stage.clientHeight * dpr);
    canvas.style.width = `${stage.clientWidth}px`;
    canvas.style.height = `${stage.clientHeight}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (layoutDone) resetGraphView(canvas, focusNode, setPanScale);
    draw();
  }

  function screenToWorld(sx, sy) {
    return {
      x: (sx - canvas.clientWidth / 2 - pan.x) / scale,
      y: (sy - canvas.clientHeight / 2 - pan.y) / scale,
    };
  }

  function zoomAt(sx, sy, factor) {
    const wx = (sx - canvas.clientWidth / 2 - pan.x) / scale;
    const wy = (sy - canvas.clientHeight / 2 - pan.y) / scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
    pan.x = sx - canvas.clientWidth / 2 - wx * scale;
    pan.y = sy - canvas.clientHeight / 2 - wy * scale;
    draw();
  }

  function nodeRadius(n) {
    return graphNodeRadius(n) * viewScale(n);
  }

  function drawEdgeLabel(text, x, y) {
    const fontSize = 10;
    ctx.font = `${fontSize}px var(--font-body), sans-serif`;
    const textW = ctx.measureText(text).width;
    const padX = 5;
    const padY = 3;
    const boxW = textW + padX * 2;
    const boxH = fontSize + padY * 2;
    ctx.fillStyle = colors.canvas;
    ctx.fillRect(x - boxW / 2, y - boxH / 2, boxW, boxH);
    ctx.fillStyle = colors.ink;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
  }

  function drawArrowhead(x, y, angle, size, color) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(
      x - size * Math.cos(angle - Math.PI / 7),
      y - size * Math.sin(angle - Math.PI / 7)
    );
    ctx.lineTo(
      x - size * Math.cos(angle + Math.PI / 7),
      y - size * Math.sin(angle + Math.PI / 7)
    );
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function drawEdge(e) {
    if (e.hidden) return;
    const geom = edgeGeometry(e);
    const { start, end, control, curved } = geom;
    const stroke = e.b.palette.border;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    if (curved) {
      ctx.quadraticCurveTo(control.x, control.y, end.x, end.y);
    } else {
      ctx.lineTo(end.x, end.y);
    }
    ctx.strokeStyle = stroke;
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = 1.6 / Math.max(scale, 0.6);
    if (e.b.dashed) ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    const tangent = curved
      ? tangentOnQuadratic(0.985, start, control, end)
      : { x: end.x - start.x, y: end.y - start.y };
    const angle = Math.atan2(tangent.y, tangent.x);
    drawArrowhead(end.x, end.y, angle, 14 / Math.max(scale, 0.6), stroke);

    const label = e.predicateLabel;
    if (!label) return;
    const labelPoint = curved
      ? pointOnQuadratic(0.5, start, control, end)
      : { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    drawEdgeLabel(label, labelPoint.x, labelPoint.y);
  }

  /**
   * Fade nodes with distance so the foreground reads as the foreground. Near
   * nodes stay fully opaque; far ones recede rather than competing.
   */
  function depthAlpha(n) {
    if (graphParams.view !== "3d") return 1;
    return Math.min(1, Math.max(0.42, (viewScale(n) - 0.6) / 0.4));
  }

  function drawNodeBody(n) {
    const r = nodeRadius(n);
    ctx.beginPath();
    ctx.arc(viewX(n), viewY(n), r, 0, Math.PI * 2);
    ctx.fillStyle = n.palette.color;
    ctx.fill();
    ctx.strokeStyle = n.palette.border;
    ctx.lineWidth = n.dashed ? 1.2 : 2;
    if (n.dashed) ctx.setLineDash([4, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
    if (selected?.id === n.id) {
      ctx.strokeStyle = colors.ink;
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
  }

  function drawNodeLabel(n) {
    const { fontSize, lineHeight, lines } = nodeLabelLayout(n);
    const depth = viewScale(n);
    // Labels behind this point are unreadable anyway, and drawing them only
    // adds clutter over the nodes in front.
    if (graphParams.view === "3d" && depth < 0.88) return;
    ctx.font = `600 ${fontSize * depth}px var(--font-body), sans-serif`;
    ctx.fillStyle = n.dashed ? colors.nodeFillMuted : colors.nodeFill;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const scaledLineHeight = lineHeight * depth;
    const blockHeight = lines.length * scaledLineHeight;
    let y = viewY(n) - blockHeight / 2 + scaledLineHeight / 2;
    for (const line of lines) {
      ctx.fillText(line, viewX(n), y);
      y += scaledLineHeight;
    }
  }

  function draw() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    projectNodes(nodes, orbit.yaw, orbit.pitch);
    ctx.save();
    ctx.translate(w / 2 + pan.x, h / 2 + pan.y);
    ctx.scale(scale, scale);
    for (const e of edges) drawEdge(e);
    if (graphParams.view === "3d") {
      // Painter's algorithm, body and label together per node. Drawing all the
      // bodies and then all the labels would let a distant node's text land on
      // top of a near node that should be hiding it.
      const ordered = [...nodes].sort((a, b) => (b._depth ?? 0) - (a._depth ?? 0));
      for (const n of ordered) {
        ctx.globalAlpha = depthAlpha(n);
        drawNodeBody(n);
        drawNodeLabel(n);
      }
      ctx.globalAlpha = 1;
    } else {
      for (const n of nodes) drawNodeBody(n);
      for (const n of nodes) drawNodeLabel(n);
    }
    ctx.restore();
  }

  function hit(pos) {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      if (Math.hypot(viewX(n) - pos.x, viewY(n) - pos.y) <= nodeRadius(n) + 5) return n;
    }
    return null;
  }

  canvas.addEventListener("pointerdown", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
    const node = hit(pos);
    pointerStart = node ? { node, x: ev.clientX, y: ev.clientY, moved: false } : null;
    const threeD = graphParams.view === "3d";
    if (node && !node.pinned && !threeD) {
      dragging = node;
      offset = { x: pos.x - node.x, y: pos.y - node.y };
    } else if (node) {
      selected = node;
      showDetail(node);
    } else if (threeD) {
      // Background drag orbits the camera rather than panning the plane.
      orbiting = { x: ev.clientX, y: ev.clientY, yaw: orbit.yaw, pitch: orbit.pitch };
    } else {
      panning = { x: ev.clientX - pan.x, y: ev.clientY - pan.y };
    }
    recentring = null;
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    const rect = canvas.getBoundingClientRect();
    if (pointerStart && Math.hypot(ev.clientX - pointerStart.x, ev.clientY - pointerStart.y) > 4) {
      pointerStart.moved = true;
    }
    if (orbiting) {
      orbit.yaw = orbiting.yaw + (ev.clientX - orbiting.x) * 0.008;
      orbit.pitch = Math.max(
        -Math.PI / 2.2,
        Math.min(Math.PI / 2.2, orbiting.pitch + (ev.clientY - orbiting.y) * 0.006)
      );
      draw();
    } else if (dragging) {
      const pos = screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
      dragging.x = pos.x - offset.x;
      dragging.y = pos.y - offset.y;
      resolveOverlaps(nodes, {
        iterations: 16,
        pinnedIds: new Set([focusNode.id].filter(Boolean)),
        minGap: graphParams.nodeMinGap,
      });
      draw();
    } else if (panning) {
      pan.x = ev.clientX - panning.x;
      pan.y = ev.clientY - panning.y;
      draw();
    }
  });
  canvas.addEventListener("pointerup", () => {
    if (pointerStart && !pointerStart.moved && pointerStart.node && !pointerStart.node.pinned) {
      selected = pointerStart.node;
      showDetail(selected);
    }
    dragging = null;
    panning = null;
    orbiting = null;
    pointerStart = null;
  });
  /**
   * Slide a node to the middle of the canvas. Projected coordinates are used
   * so this centres what is actually on screen, in 3D as well as 2D.
   */
  function centreOnNode(node) {
    if (!node) return;
    const targetX = -viewX(node) * scale;
    const targetY = -viewY(node) * scale;
    const startX = pan.x;
    const startY = pan.y;
    const startedAt = performance.now();
    const duration = 260;
    // A jump is disorienting when the graph is dense: easing the pan keeps the
    // node you picked traceable on its way to the centre.
    const frame = (now) => {
      if (recentring !== frame) return;
      const t = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - (1 - t) ** 3;
      pan.x = startX + (targetX - startX) * eased;
      pan.y = startY + (targetY - startY) * eased;
      draw();
      if (t < 1) requestAnimationFrame(frame);
      else recentring = null;
    };
    recentring = frame;
    requestAnimationFrame(frame);
  }

  canvas.addEventListener("dblclick", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const node = hit(screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top));
    if (!node) return;
    selected = node;
    showDetail(node);
    centreOnNode(node);
  });

  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    zoomAt(ev.clientX - rect.left, ev.clientY - rect.top, ev.deltaY < 0 ? 1.1 : 0.9);
  }, { passive: false });

  root.querySelector("#graph-zoom-in")?.addEventListener("click", () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 1.15));
  root.querySelector("#graph-zoom-out")?.addEventListener("click", () => zoomAt(canvas.clientWidth / 2, canvas.clientHeight / 2, 0.87));
  root.querySelector("#graph-zoom-reset")?.addEventListener("click", () => {
    resetGraphView(canvas, focusNode, setPanScale);
    selected = focusNode;
    showDetail(focusNode);
    draw();
  });

  window.addEventListener("resize", resize);
  resize();
  selected = focusNode;
  renderDetail(focusNode);
  if (graphParams.physics) {
    stopPhysics = runClassPhysics(nodes, edges, focusNode, {
      onTick: draw,
      onEnd: () => {
        resetGraphView(canvas, focusNode, setPanScale);
        draw();
      },
    });
  } else {
    // Physics off: the seeded layout is the layout.
    resetGraphView(canvas, focusNode, setPanScale);
    draw();
  }

  return () => {
    window.removeEventListener("resize", resize);
    stopPhysics?.();
  };
}

function groupInstancesByType(typeOptions, allInstances) {
  const byType = new Map(typeOptions.map((type) => [type.label, []]));
  for (const instance of allInstances) {
    const list = byType.get(instance.type);
    if (list) list.push(instance);
  }
  return typeOptions.map((type) => ({
    ...type,
    instances: byType.get(type.label) || [],
  }));
}

function renderProcessFilter(
  typeOptions,
  allInstances,
  hiddenProcessTypes,
  hiddenProcessInstances,
  expandedProcessTypes
) {
  const groups = groupInstancesByType(typeOptions, allInstances);
  const items = groups
    .map((group) => {
      const def = bfoColor(group.bucket);
      const typeChecked = hiddenProcessTypes.has(group.label) ? "" : " checked";
      const expanded = expandedProcessTypes.has(group.label);
      const typeHidden = hiddenProcessTypes.has(group.label);
      const instanceItems = group.instances
        .map((instance) => {
          const checked = hiddenProcessInstances.has(instance.id) ? "" : " checked";
          return `<li><label class="graph-process-instance-label${typeHidden ? " is-muted" : ""}">
            <input type="checkbox" data-process-instance="${esc(instance.id)}"${checked}${typeHidden ? " disabled" : ""} />
            <span class="graph-class-name">${esc(instance.label)}</span>
          </label></li>`;
        })
        .join("");
      return `<li class="graph-process-group">
        <div class="graph-process-type-row">
          <label>
            <input type="checkbox" data-process-type="${esc(group.label)}"${typeChecked} />
            <i class="graph-swatch" style="background:${def.color};border:1px solid ${def.border}"></i>
            <span class="graph-class-name">${esc(group.label)}</span>
            <span class="graph-class-count">${group.instances.length}</span>
          </label>
          <button type="button" class="graph-process-expand" data-process-type-expand="${esc(group.label)}"
            aria-expanded="${expanded ? "true" : "false"}" aria-label="Show ${esc(group.label)} instances"
            ${group.instances.length === 0 ? " disabled" : ""}>
            <svg class="graph-process-expand-chevron" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6" /></svg>
          </button>
        </div>
        <ul class="graph-process-instance-list"${expanded ? "" : " hidden"}>${instanceItems || `<li class="muted">No instances</li>`}</ul>
      </li>`;
    })
    .join("");
  const visibleCount = allInstances.filter(
    (instance) =>
      !hiddenProcessTypes.has(instance.type) && !hiddenProcessInstances.has(instance.id)
  ).length;
  const summary =
    allInstances.length === 0
      ? "None"
      : visibleCount === allInstances.length
        ? `All ${allInstances.length}`
        : `${visibleCount} of ${allInstances.length}`;
  return `<div class="graph-processes"><span>Processes</span>
    <button type="button" class="graph-processes-toggle" id="graph-processes-toggle" aria-expanded="false" aria-haspopup="true"${allInstances.length === 0 ? " disabled" : ""}>
      <span>${esc(summary)}</span>
      <svg class="graph-processes-chevron" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6" /></svg>
    </button>
    <div class="graph-processes-menu" id="graph-processes-menu" hidden>
      <ul class="graph-process-groups">${items || `<li class="muted">No processes at this distance</li>`}</ul>
      <div class="graph-processes-actions">
        <button type="button" data-processes-action="all"${allInstances.length === 0 ? " disabled" : ""}>Select all</button>
        <button type="button" data-processes-action="none"${allInstances.length === 0 ? " disabled" : ""}>Clear all</button>
      </div>
    </div>
  </div>`;
}

function renderClassFilter(
  typeOptions,
  allInstances,
  hiddenClassTypes,
  hiddenClassInstances,
  expandedClassTypes
) {
  const groups = groupInstancesByType(typeOptions, allInstances);
  const items = groups
    .map((group) => {
      const def = bfoColor(group.bucket);
      const typeChecked = hiddenClassTypes.has(group.label) ? "" : " checked";
      const expanded = expandedClassTypes.has(group.label);
      const typeHidden = hiddenClassTypes.has(group.label);
      const instanceItems = group.instances
        .map((instance) => {
          const checked = hiddenClassInstances.has(instance.id) ? "" : " checked";
          return `<li><label class="graph-class-instance-label${typeHidden ? " is-muted" : ""}">
            <input type="checkbox" data-class-instance="${esc(instance.id)}"${checked}${typeHidden ? " disabled" : ""} />
            <span class="graph-class-name">${esc(instance.label)}</span>
          </label></li>`;
        })
        .join("");
      return `<li class="graph-class-group">
        <div class="graph-class-type-row">
          <label>
            <input type="checkbox" data-class-type="${esc(group.label)}"${typeChecked} />
            <i class="graph-swatch" style="background:${def.color};border:1px solid ${def.border}"></i>
            <span class="graph-class-name">${esc(group.label)}</span>
            <span class="graph-class-count">${group.instances.length}</span>
          </label>
          <button type="button" class="graph-class-expand" data-class-type-expand="${esc(group.label)}"
            aria-expanded="${expanded ? "true" : "false"}" aria-label="Show ${esc(group.label)} instances"
            ${group.instances.length === 0 ? " disabled" : ""}>
            <svg class="graph-class-expand-chevron" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6" /></svg>
          </button>
        </div>
        <ul class="graph-class-instance-list"${expanded ? "" : " hidden"}>${instanceItems || `<li class="muted">No instances</li>`}</ul>
      </li>`;
    })
    .join("");
  const visibleCount = allInstances.filter(
    (instance) =>
      !hiddenClassTypes.has(instance.type) && !hiddenClassInstances.has(instance.id)
  ).length;
  const summary =
    allInstances.length === 0
      ? "None"
      : visibleCount === allInstances.length
        ? `All ${allInstances.length}`
        : `${visibleCount} of ${allInstances.length}`;
  return `<div class="graph-classes"><span>Continuants</span>
    <button type="button" class="graph-classes-toggle" id="graph-classes-toggle" aria-expanded="false" aria-haspopup="true"${allInstances.length === 0 ? " disabled" : ""}>
      <span>${esc(summary)}</span>
      <svg class="graph-classes-chevron" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6" /></svg>
    </button>
    <div class="graph-classes-menu" id="graph-classes-menu" hidden>
      <ul class="graph-class-groups">${items || `<li class="muted">No continuants at this distance</li>`}</ul>
      <div class="graph-classes-actions">
        <button type="button" data-classes-action="all"${allInstances.length === 0 ? " disabled" : ""}>Select all</button>
        <button type="button" data-classes-action="none"${allInstances.length === 0 ? " disabled" : ""}>Clear all</button>
      </div>
    </div>
  </div>`;
}

function formatParamValue(key, value) {
  const def = GRAPH_PARAM_DEFS[key];
  const unit = def.unit || "";
  return def.step < 1 ? `${Number(value).toFixed(2)}${unit}` : `${value}${unit}`;
}

function renderParamsPanel(params, distance, open) {
  const rows = Object.entries(GRAPH_PARAM_DEFS)
    .map(([key, def]) => {
      if (def.type === "select") {
        const options = def.options
          .map(
            (option) =>
              `<option value="${option.value}"${params[key] === option.value ? " selected" : ""}>${esc(option.label)}</option>`
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
    <button type="button" class="graph-params-toggle" id="graph-params-toggle"
      aria-expanded="${open ? "true" : "false"}" aria-haspopup="true"
      title="Graph parameters" aria-label="Graph parameters">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
        <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
      </svg>
    </button>
    <div class="graph-params-menu" id="graph-params-menu" ${open ? "" : "hidden"}>
      <div class="graph-params-tabs" role="tablist">
        ${GRAPH_VIEWS.map(
          (view) => `<button type="button" role="tab" data-view="${view}"
            aria-selected="${params.view === view ? "true" : "false"}"
            class="${params.view === view ? "is-active" : ""}">${esc(GRAPH_VIEW_LABELS[view])}</button>`
        ).join("")}
      </div>
      <p class="graph-params-note">${
        params.view === "3d"
          ? "Every cluster gets its own depth, projected in perspective. Drag the background to orbit; nodes cannot be dragged while orbiting."
          : "The flat view. Drag the background to pan, drag a node to move it."
      }</p>
      <div class="graph-params-grid">
        <label class="graph-param">
          <span class="graph-param-head">Distance <strong data-param-value="distance">${distance}</strong></span>
          <input type="range" data-param="distance" min="1" max="3" step="1" value="${distance}" />
          <em>${esc(DISTANCE_HINT)}</em>
        </label>
        ${rows}
      </div>
      <button type="button" id="graph-params-reset">Reset to defaults</button>
    </div>
  </div>`;
}

function renderLegend() {
  const items = BFO_SEVEN.map(
    (b) => `<span><i class="graph-swatch" style="background:${b.color};border:1px solid ${b.border}"></i> ${esc(b.label)}</span>`
  ).join("");
  return `<strong>BFO buckets</strong>${items}`;
}

function readStoredHiddenClassTypes() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(HIDDEN_CLASS_TYPES_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function readStoredHiddenClassInstances() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(HIDDEN_CLASS_INSTANCES_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function readStoredHiddenProcessTypes() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(HIDDEN_PROCESS_TYPES_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function readStoredHiddenProcesses() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(HIDDEN_PROCESSES_KEY) || "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

// Landing on an empty canvas hides what the page is for, so the graph opens on
// a person with a full working history rather than on a prompt to search.
let DEFAULT_PERSON_LABEL;
let DEFAULT_DISTANCE;

function defaultPerson(people) {
  return (
    people.find((person) => person.label === DEFAULT_PERSON_LABEL) ||
    people.find((person) => person.kind === "employee") ||
    people[0] ||
    null
  );
}

function graphFiltersFromUrl(people, fallbackDistance) {
  const params = new URLSearchParams(window.location.search);
  const personParam = params.get("person");
  const selectedPerson = personParam
    ? people.find((person) => person.id === personParam || person.label === personParam)
    : defaultPerson(people);
  const distanceParam = Number(params.get("distance"));
  const distance = [1, 2, 3].includes(distanceParam) ? distanceParam : fallbackDistance;
  return {
    selectedId: selectedPerson?.id || null,
    distance,
  };
}

/** Min/max ISO dates from temporal regions on a person's visible process roots. */
function temporalRangeForPerson(adj, personId, hopDistance) {
  const reachable = collectVisibleGraph(adj, personId, hopDistance);
  const temporalProcesses = collectProcessTemporalRecords(reachable, { isProcessRoot });
  return computeGlobalDateRange(temporalProcesses);
}

function resetGraphParamsToDefaults() {
  graphState = {
    view: DEFAULT_GRAPH_VIEW,
    byView: Object.fromEntries(GRAPH_VIEWS.map((view) => [view, defaultGraphParams(view)])),
  };
  applyGraphView(DEFAULT_GRAPH_VIEW);
  sessionStorage.setItem(PARAMS_KEY, JSON.stringify(graphState));
}

function entitySlugFromPathname() {
  const segments = window.location.pathname.split("/").filter(Boolean);
  if (segments.length >= 2) return segments[0];
  if (segments.length === 1 && !CONFIGURED_PAGE_URLS.has(segments[0])) {
    return segments[0];
  }
  return DEFAULT_ENTITY_SLUG;
}

function syncGraphFiltersToUrl(personId, distance) {
  const url = new URL(window.location.href);
  url.pathname = `/${entitySlugFromPathname()}/${GRAPH_PAGE_URL}`;
  if (personId) url.searchParams.set("person", personId);
  else url.searchParams.delete("person");
  url.searchParams.set("distance", String(distance));
  window.history.replaceState(window.history.state, "", url);
}

export function mountGraphPage(el, data) {
  const adj = buildGraphIndex(data);
  const lookup = {
    peopleById: adj.peopleById,
    processesById: adj.processesById,
    entitiesById: adj.entitiesById,
    workingHubByPerson: adj.workingHubByPerson,
  };
  const people = [...(data.people || [])].sort((a, b) => a.label.localeCompare(b.label));
  const storedDistance = Math.min(
    3,
    Math.max(1, Number(sessionStorage.getItem(DISTANCE_KEY)) || DEFAULT_DISTANCE)
  );
  const initialFilters = graphFiltersFromUrl(people, storedDistance);
  let dateRangeStart = null;
  let dateRangeEnd = null;
  let selectedId = initialFilters.selectedId;
  let distance = initialFilters.distance;
  const lastPersonId = sessionStorage.getItem(LAST_PERSON_KEY);
  const personChanged = Boolean(selectedId && selectedId !== lastPersonId);
  let hiddenClassTypes;
  let hiddenClassInstances;
  let hiddenProcessTypes;
  let hiddenProcessInstances;
  if (personChanged) {
    resetGraphParamsToDefaults();
    distance = DEFAULT_DISTANCE;
    sessionStorage.setItem(DISTANCE_KEY, String(distance));
    hiddenClassTypes = new Set();
    hiddenClassInstances = new Set();
    hiddenProcessTypes = new Set();
    hiddenProcessInstances = new Set();
  } else {
    hiddenClassTypes = new Set(readStoredHiddenClassTypes());
    hiddenClassInstances = new Set(readStoredHiddenClassInstances());
    hiddenProcessTypes = new Set(readStoredHiddenProcessTypes());
    hiddenProcessInstances = new Set(readStoredHiddenProcesses());
  }
  if (selectedId) {
    const initialRange = temporalRangeForPerson(adj, selectedId, distance);
    dateRangeStart = initialRange.min;
    dateRangeEnd = initialRange.max;
    sessionStorage.setItem(LAST_PERSON_KEY, selectedId);
  }
  let classMenuOpen = false;
  let processMenuOpen = false;
  let expandedProcessTypes = new Set();
  let expandedClassTypes = new Set();
  // Survives the repaint each parameter change triggers, so the panel stays
  // open while several values are being tuned.
  let paramsOpen = false;
  let disposeCanvas = null;
  let disposeDateSlicer = null;
  syncGraphFiltersToUrl(selectedId, distance);

  function persistParams() {
    // Mirror the live values back into the active view's slot before saving,
    // so the other view's settings survive untouched.
    const { view, ...values } = graphParams;
    graphState.view = view;
    graphState.byView[view] = { ...values };
    sessionStorage.setItem(PARAMS_KEY, JSON.stringify(graphState));
  }

  function persistHiddenClassTypes() {
    sessionStorage.setItem(HIDDEN_CLASS_TYPES_KEY, JSON.stringify([...hiddenClassTypes]));
  }

  function persistHiddenClassInstances() {
    sessionStorage.setItem(
      HIDDEN_CLASS_INSTANCES_KEY,
      JSON.stringify([...hiddenClassInstances])
    );
  }

  function persistHiddenProcessTypes() {
    sessionStorage.setItem(HIDDEN_PROCESS_TYPES_KEY, JSON.stringify([...hiddenProcessTypes]));
  }

  function persistHiddenProcessInstances() {
    sessionStorage.setItem(HIDDEN_PROCESSES_KEY, JSON.stringify([...hiddenProcessInstances]));
  }

  function pruneHiddenClassTypes(typeOptions) {
    const liveTypes = new Set(typeOptions.map((option) => option.label));
    hiddenClassTypes = new Set([...hiddenClassTypes].filter((type) => liveTypes.has(type)));
  }

  function pruneHiddenClassInstances(instanceOptions, typeOptions) {
    const liveIds = new Set(instanceOptions.map((option) => option.id));
    hiddenClassInstances = new Set(
      [...hiddenClassInstances].filter((id) => liveIds.has(id))
    );
    const liveTypes = new Set(typeOptions.map((option) => option.label));
    expandedClassTypes = new Set(
      [...expandedClassTypes].filter((type) => liveTypes.has(type))
    );
  }

  function pruneHiddenProcessTypes(typeOptions) {
    const liveTypes = new Set(typeOptions.map((option) => option.label));
    hiddenProcessTypes = new Set([...hiddenProcessTypes].filter((type) => liveTypes.has(type)));
  }

  function pruneHiddenProcessInstances(instanceOptions, typeOptions) {
    const liveIds = new Set(instanceOptions.map((option) => option.id));
    hiddenProcessInstances = new Set(
      [...hiddenProcessInstances].filter((id) => liveIds.has(id))
    );
    const liveTypes = new Set(typeOptions.map((option) => option.label));
    expandedProcessTypes = new Set(
      [...expandedProcessTypes].filter((type) => liveTypes.has(type))
    );
  }

  function persistDateSlicerState() {
    if (!selectedId) return;
    persistDateSlicer(`${DATE_SLICER_CONFIG.storageKey}:${selectedId}`, dateRangeStart, dateRangeEnd);
  }

  function resetGraphStateForPerson(personId) {
    distance = DEFAULT_DISTANCE;
    sessionStorage.setItem(DISTANCE_KEY, String(distance));
    resetGraphParamsToDefaults();

    hiddenClassTypes = new Set();
    hiddenClassInstances = new Set();
    hiddenProcessTypes = new Set();
    hiddenProcessInstances = new Set();
    expandedProcessTypes = new Set();
    expandedClassTypes = new Set();
    persistHiddenClassTypes();
    persistHiddenClassInstances();
    persistHiddenProcessTypes();
    persistHiddenProcessInstances();

    processMenuOpen = false;
    classMenuOpen = false;
    paramsOpen = false;

    const range = temporalRangeForPerson(adj, personId, distance);
    dateRangeStart = range.min;
    dateRangeEnd = range.max;
    sessionStorage.setItem(LAST_PERSON_KEY, personId);
    persistDateSlicerState();
  }

  if (personChanged) {
    persistHiddenClassTypes();
    persistHiddenClassInstances();
    persistHiddenProcessTypes();
    persistHiddenProcessInstances();
  }

  function paint() {
    const person = people.find((p) => p.id === selectedId) || null;
    const reachable = person ? collectVisibleGraph(adj, person.id, distance) : null;
    const temporalProcesses = reachable
      ? collectProcessTemporalRecords(reachable, { isProcessRoot })
      : [];
    const dateRange = computeGlobalDateRange(temporalProcesses);
    if (dateRange.min && !dateRangeStart) dateRangeStart = dateRange.min;
    if (dateRange.max && !dateRangeEnd) dateRangeEnd = dateRange.max;
    if (dateRange.min && dateRangeStart && dateRangeStart < dateRange.min) {
      dateRangeStart = dateRange.min;
    }
    if (dateRange.max && dateRangeEnd && dateRangeEnd > dateRange.max) {
      dateRangeEnd = dateRange.max;
    }
    if (dateRangeStart && dateRangeEnd && dateRangeStart > dateRangeEnd) {
      dateRangeEnd = dateRange.max || dateRangeEnd;
    }
    const dateFiltered = reachable
      ? applyDateFilter(
          reachable,
          dateRangeStart,
          dateRangeEnd,
          dateRange,
          person.id,
          {
            visibleProcessOptions,
            findProcessRecord,
            applyProcessFilter,
          }
        )
      : null;
    const allProcessInstances = dateFiltered ? visibleProcessOptions(dateFiltered) : [];
    const processTypeOptions = visibleProcessTypeOptions(allProcessInstances);
    pruneHiddenProcessTypes(processTypeOptions);
    pruneHiddenProcessInstances(allProcessInstances, processTypeOptions);
    const processFiltered = dateFiltered
      ? applyProcessFilter(
          dateFiltered,
          hiddenProcessInstances,
          hiddenProcessTypes,
          person.id
        )
      : null;
    const allClassInstances = processFiltered
      ? visibleClassInstanceOptions(processFiltered, person.id)
      : [];
    const classTypeOptions = visibleClassTypeOptions(allClassInstances);
    pruneHiddenClassTypes(classTypeOptions);
    pruneHiddenClassInstances(allClassInstances, classTypeOptions);
    const visible = processFiltered
      ? applyClassFilter(
          processFiltered,
          hiddenClassInstances,
          hiddenClassTypes,
          person.id
        )
      : null;

    const toolbarLayout = graphParams.toolbarLayout === "column" ? "column" : "row";

    el.innerHTML = `
      ${
        person
          ? `<div class="graph-page"><div class="graph-body">
              <div class="graph-stage" id="graph-stage">
                <canvas id="graph-canvas"></canvas>
                <div class="graph-toolbar graph-toolbar--${toolbarLayout}">
                  <label class="graph-search"><span>Person</span>
                    <input type="search" id="graph-person-search" placeholder="Search people…" value="${esc(person?.label || "")}" autocomplete="off" />
                    <ul class="graph-suggestions" id="graph-suggestions" hidden></ul>
                  </label>
                  ${renderProcessFilter(
                    processTypeOptions,
                    allProcessInstances,
                    hiddenProcessTypes,
                    hiddenProcessInstances,
                    expandedProcessTypes
                  )}
                  ${renderDateSlicer({
                    esc,
                    globalRange: dateRange,
                    selectedStart: dateRangeStart,
                    selectedEnd: dateRangeEnd,
                  })}
                  ${renderClassFilter(
                    classTypeOptions,
                    allClassInstances,
                    hiddenClassTypes,
                    hiddenClassInstances,
                    expandedClassTypes
                  )}
                </div>
                ${graphParams.legend ? `<div class="graph-legend">${renderLegend()}</div>` : ""}
                <div class="graph-controls">
                  <div class="graph-zoom"><button type="button" id="graph-zoom-in" title="Zoom in">+</button><button type="button" id="graph-zoom-out" title="Zoom out">−</button><button type="button" id="graph-zoom-reset" title="Reset view">⟲</button></div>
                  ${renderParamsPanel(graphParams, distance, paramsOpen)}
                </div>
                <p class="graph-hint">${graphParams.view === "3d" ? "Drag to orbit" : "Focus at center · drag to pan"} · every other node is simulated · double-click to centre · scroll to zoom</p>
              </div>
              <aside class="graph-detail" id="graph-detail"></aside>
            </div></div>`
          : `<div class="graph-page"><div class="graph-toolbar">
              <label class="graph-search"><span>Person</span>
                <input type="search" id="graph-person-search" placeholder="Search people…" value="" autocomplete="off" />
                <ul class="graph-suggestions" id="graph-suggestions" hidden></ul>
              </label>
            </div><div class="graph-empty panel"><h2>Select a person</h2><p>Try <strong>Alice Dupont</strong>, <strong>Emma Petit</strong>, or <strong>Grace Lambert</strong> to decompose their acts of working.</p></div></div>`
      }`;

    const input = el.querySelector("#graph-person-search");
    const suggestions = el.querySelector("#graph-suggestions");
    const openSuggestions = (query) => {
      const q = query.trim().toLowerCase();
      const hits = people.filter((p) => !q || p.label.toLowerCase().includes(q)).slice(0, 8);
      suggestions.innerHTML = hits.map((p) => `<li data-person="${esc(p.id)}"><strong>${esc(p.label)}</strong></li>`).join("") || `<li class="muted">No matches</li>`;
      suggestions.hidden = false;
    };
    input.addEventListener("focus", () => openSuggestions(input.value));
    input.addEventListener("input", () => openSuggestions(input.value));
    suggestions.addEventListener("click", (e) => {
      const li = e.target.closest("[data-person]");
      if (!li) return;
      selectedId = li.dataset.person;
      resetGraphStateForPerson(selectedId);
      syncGraphFiltersToUrl(selectedId, distance);
      paint();
    });
    const paramsToggle = el.querySelector("#graph-params-toggle");
    const paramsMenu = el.querySelector("#graph-params-menu");
    paramsToggle?.addEventListener("click", () => {
      paramsOpen = !paramsOpen;
      paramsMenu.hidden = !paramsOpen;
      paramsToggle.setAttribute("aria-expanded", paramsOpen ? "true" : "false");
    });

    if (disposeDateSlicer) disposeDateSlicer();
    disposeDateSlicer = mountDateRangeSlicer(el.querySelector("#graph-date-slicer"), {
      onRangeChange: (start, end) => {
        dateRangeStart = start;
        dateRangeEnd = end;
        persistDateSlicerState();
        paint();
      },
    });

    // `input` updates the readout on every frame of the drag; `change` - once
    // the thumb is released - is what repaints, so dragging a slider does not
    // rebuild the whole canvas dozens of times.
    for (const input of el.querySelectorAll("[data-param]")) {
      const key = input.dataset.param;
      input.addEventListener("input", (e) => {
        if (GRAPH_PARAM_DEFS[key]?.type === "select") return;
        const readout = el.querySelector(`[data-param-value="${key}"]`);
        if (!readout) return;
        readout.textContent =
          key === "distance"
            ? String(Number(e.target.value) || 1)
            : formatParamValue(key, Number(e.target.value));
      });
      input.addEventListener("change", (e) => {
        if (key === "distance") {
          distance = Number(e.target.value) || 1;
          sessionStorage.setItem(DISTANCE_KEY, String(distance));
          syncGraphFiltersToUrl(selectedId, distance);
          const range = temporalRangeForPerson(adj, selectedId, distance);
          if (range.min) dateRangeStart = range.min;
          if (range.max) dateRangeEnd = range.max;
          persistDateSlicerState();
        } else if (GRAPH_PARAM_DEFS[key]?.type === "toggle") {
          graphParams[key] = e.target.checked;
          persistParams();
        } else if (GRAPH_PARAM_DEFS[key]?.type === "select") {
          graphParams[key] = e.target.value;
          if (key === "toolbarLayout") {
            for (const view of GRAPH_VIEWS) {
              graphState.byView[view] = {
                ...graphState.byView[view],
                toolbarLayout: e.target.value,
              };
            }
          }
          persistParams();
        } else {
          graphParams[key] = Number(e.target.value);
          persistParams();
        }
        paint();
      });
    }

    for (const tab of el.querySelectorAll(".graph-params-tabs [data-view]")) {
      tab.addEventListener("click", () => {
        if (tab.dataset.view === graphParams.view) return;
        // Save what the current view is showing before swapping to the other.
        persistParams();
        applyGraphView(tab.dataset.view);
        persistParams();
        paint();
      });
    }

    el.querySelector("#graph-params-reset")?.addEventListener("click", () => {
      Object.assign(graphParams, defaultGraphParams(graphParams.view));
      persistParams();
      paint();
    });
    const processToggle = el.querySelector("#graph-processes-toggle");
    const processMenu = el.querySelector("#graph-processes-menu");
    if (processToggle && processMenu) {
      const setProcessMenuOpen = (open) => {
        processMenuOpen = open;
        processMenu.hidden = !open;
        processToggle.setAttribute("aria-expanded", String(open));
      };
      setProcessMenuOpen(processMenuOpen);
      processToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (processToggle.disabled) return;
        setProcessMenuOpen(processMenu.hidden);
      });
      processMenu.addEventListener("click", (e) => e.stopPropagation());
      processMenu.addEventListener("click", (e) => {
        const expand = e.target.closest("[data-process-type-expand]");
        if (!expand || expand.disabled) return;
        e.stopPropagation();
        const type = expand.dataset.processTypeExpand;
        if (expandedProcessTypes.has(type)) expandedProcessTypes.delete(type);
        else expandedProcessTypes.add(type);
        paint();
      });
      processMenu.addEventListener("change", (e) => {
        const typeBox = e.target.closest("input[data-process-type]");
        if (typeBox) {
          if (typeBox.checked) hiddenProcessTypes.delete(typeBox.dataset.processType);
          else hiddenProcessTypes.add(typeBox.dataset.processType);
          persistHiddenProcessTypes();
          paint();
          return;
        }
        const instanceBox = e.target.closest("input[data-process-instance]");
        if (!instanceBox || instanceBox.disabled) return;
        if (instanceBox.checked) hiddenProcessInstances.delete(instanceBox.dataset.processInstance);
        else hiddenProcessInstances.add(instanceBox.dataset.processInstance);
        persistHiddenProcessInstances();
        paint();
      });
      processMenu.querySelectorAll("[data-processes-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.disabled) return;
          if (button.dataset.processesAction === "none") {
            for (const option of processTypeOptions) hiddenProcessTypes.add(option.label);
            for (const option of allProcessInstances) hiddenProcessInstances.add(option.id);
          } else {
            hiddenProcessTypes = new Set();
            hiddenProcessInstances = new Set();
          }
          persistHiddenProcessTypes();
          persistHiddenProcessInstances();
          paint();
        });
      });
    }

    const classToggle = el.querySelector("#graph-classes-toggle");
    const classMenu = el.querySelector("#graph-classes-menu");
    if (classToggle && classMenu) {
      const setClassMenuOpen = (open) => {
        classMenuOpen = open;
        classMenu.hidden = !open;
        classToggle.setAttribute("aria-expanded", String(open));
      };
      setClassMenuOpen(classMenuOpen);
      classToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (classToggle.disabled) return;
        setClassMenuOpen(classMenu.hidden);
      });
      classMenu.addEventListener("click", (e) => e.stopPropagation());
      classMenu.addEventListener("click", (e) => {
        const expand = e.target.closest("[data-class-type-expand]");
        if (!expand || expand.disabled) return;
        e.stopPropagation();
        const type = expand.dataset.classTypeExpand;
        if (expandedClassTypes.has(type)) expandedClassTypes.delete(type);
        else expandedClassTypes.add(type);
        paint();
      });
      classMenu.addEventListener("change", (e) => {
        const typeBox = e.target.closest("input[data-class-type]");
        if (typeBox) {
          if (typeBox.checked) hiddenClassTypes.delete(typeBox.dataset.classType);
          else hiddenClassTypes.add(typeBox.dataset.classType);
          persistHiddenClassTypes();
          paint();
          return;
        }
        const instanceBox = e.target.closest("input[data-class-instance]");
        if (!instanceBox || instanceBox.disabled) return;
        if (instanceBox.checked) hiddenClassInstances.delete(instanceBox.dataset.classInstance);
        else hiddenClassInstances.add(instanceBox.dataset.classInstance);
        persistHiddenClassInstances();
        paint();
      });
      classMenu.querySelectorAll("[data-classes-action]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.disabled) return;
          if (button.dataset.classesAction === "none") {
            for (const option of classTypeOptions) hiddenClassTypes.add(option.label);
            for (const option of allClassInstances) hiddenClassInstances.add(option.id);
          } else {
            hiddenClassTypes = new Set();
            hiddenClassInstances = new Set();
          }
          persistHiddenClassTypes();
          persistHiddenClassInstances();
          paint();
        });
      });
    }

    if (disposeCanvas) disposeCanvas();
    if (person) {
      disposeCanvas = mountGraphCanvas(el, {
        focusPerson: person,
        visible,
        lookup,
        workingHubByPerson: adj.workingHubByPerson,
      });
    }
  }

  const closeFilterMenus = () => {
    if (classMenuOpen) {
      classMenuOpen = false;
      const menu = el.querySelector("#graph-classes-menu");
      const toggle = el.querySelector("#graph-classes-toggle");
      if (menu) menu.hidden = true;
      toggle?.setAttribute("aria-expanded", "false");
    }
    if (processMenuOpen) {
      processMenuOpen = false;
      const menu = el.querySelector("#graph-processes-menu");
      const toggle = el.querySelector("#graph-processes-toggle");
      if (menu) menu.hidden = true;
      toggle?.setAttribute("aria-expanded", "false");
    }
  };
  document.addEventListener("click", closeFilterMenus);

  paint();
  return () => {
    document.removeEventListener("click", closeFilterMenus);
    if (disposeDateSlicer) disposeDateSlicer();
    if (disposeCanvas) disposeCanvas();
  };
}

/** @param {HTMLElement} el @param {{ loadJson: (rel: string) => Promise<object> }} ctx */
export async function mountPage(el, ctx) {
  configureGraph(ctx.config);
  const data = await ctx.loadJson("graph/index.json");
  return mountGraphPage(el, data);
}
