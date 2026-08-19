import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const cockpitRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const graphModule = pathToFileURL(
  path.join(cockpitRoot, "web/components/pages/graph/GraphPage.js")
).href;
const dataPath = path.join(cockpitRoot, "data/entities/demo/graph/index.json");

const {
  buildGraphIndex,
  collectVisibleGraph,
  visibleClassOptions,
  applyClassFilter,
  suppressOldProcesses,
  layoutGraphNodes,
  countOverlaps,
  settleClassPhysicsSync,
  PROCESS_ROOT_RADIUS,
  MAX_PROCESSES_PER_CLASS,
} = await import(graphModule);

const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const adj = buildGraphIndex(data);
adj.ledgerProcesses = data.ledgerProcesses || [];
adj.allRelations = data.allRelations || data.relations || [];

// Same shape the app builds in mountGraphPage.
const lookup = {
  peopleById: adj.peopleById,
  processesById: adj.processesById,
  ledgerProcessesById: adj.ledgerProcessesById,
  sourcesById: adj.sourcesById,
  entitiesById: adj.entitiesById,
  birthHubByPerson: adj.birthHubByPerson,
  workingHubByPerson: adj.workingHubByPerson,
};

const personId = "Emma Petit";
const person = adj.peopleById[personId];
const expected = {
  1: {
    min: 5,
    mustInclude: ["Birth", "Working", "Christine Example", "Pascal Example"],
    mustExclude: ["Alice Dupont", "Marie Example", "Henri Example"],
  },
  2: {
    min: 19,
    mustInclude: ["Alice Dupont", "05/12/1989", "Naas.ai"],
    mustExclude: ["Marie Example", "Henri Example"],
  },
  3: {
    min: 29,
    mustInclude: ["Alice Dupont", "Marie Example", "Henri Example"],
  },
};

// Ledger provenance nodes appear only when "Show ledger sources" is on, and only at the true
// graph distance of their attachment point: `registers birth` runs Registration → Birth, so the
// registration is 2 hops from the focus person and the declaration act behind it is 3.
const LEDGER_LABELS = ["Birth Registration Process", "Birth Declaration Act"];
const LEDGER_EXPECTED_AT = {
  1: [],
  2: ["Birth Registration Process"],
  3: ["Birth Registration Process", "Birth Declaration Act"],
};

let failed = false;
const fail = (message) => {
  console.log(`FAIL ${message}`);
  failed = true;
};

const counts = new Map();

for (const showSources of [false, true]) {
  const tag = showSources ? "sources=on" : "sources=off";

  const optionLabelsByDistance = new Map();

  for (const distance of [1, 2, 3]) {
    const visible = collectVisibleGraph(adj, personId, distance, showSources);

    // Every process the graph shows must carry a temporal region, and no class
    // may exceed the per-class recency cap.
    const processRecords = [
      ...visible.entities,
      ...visible.processes,
      ...(visible.sources || []),
    ].filter((record) => record.bfoBucket === "Process");
    const undated = processRecords.filter((record) => !record.startedAt || !record.endedAt);
    if (undated.length > 0) {
      fail(
        `${tag} d=${distance}: ${undated.length} process(es) without a bounded temporal region ` +
          `(${[...new Set(undated.map((r) => r.classLabel))].join(", ")})`
      );
    }
    const perClass = new Map();
    for (const record of processRecords) {
      perClass.set(record.classLabel, (perClass.get(record.classLabel) || 0) + 1);
    }
    for (const [classLabel, count] of perClass.entries()) {
      if (count > MAX_PROCESSES_PER_CLASS) {
        fail(
          `${tag} d=${distance}: ${count} ${classLabel} processes exceeds the ` +
            `cap of ${MAX_PROCESSES_PER_CLASS}`
        );
      }
    }

    // The class filter lists exactly what this distance reaches, and hiding a
    // class removes its nodes without leaving dangling relations.
    const options = visibleClassOptions(visible);
    optionLabelsByDistance.set(distance, new Set(options.map((o) => o.label)));
    const optionTotal = options.reduce((sum, o) => sum + o.count, 0);
    const nodeTotal =
      visible.people.length +
      visible.entities.length +
      visible.processes.length +
      (visible.sources || []).length;
    if (optionTotal !== nodeTotal) {
      fail(
        `${tag} d=${distance}: class options count ${optionTotal} != ${nodeTotal} visible nodes`
      );
    }
    for (const option of options) {
      const filtered = applyClassFilter(visible, new Set([option.label]), personId);
      const remaining = [
        ...filtered.people,
        ...filtered.entities,
        ...filtered.processes,
        ...(filtered.sources || []),
      ];
      const leaked = remaining.filter(
        (record) => record.classLabel === option.label && record.id !== personId
      );
      if (leaked.length > 0) {
        fail(`${tag} d=${distance}: hiding ${option.label} left ${leaked.length} node(s) behind`);
      }
      if (!filtered.people.some((p) => p.id === personId)) {
        fail(`${tag} d=${distance}: hiding ${option.label} dropped the focus person`);
      }
      const liveIds = new Set(remaining.map((record) => record.id));
      const dangling = filtered.relations.filter(
        (rel) => !liveIds.has(rel.from) || !liveIds.has(rel.to)
      );
      if (dangling.length > 0) {
        fail(
          `${tag} d=${distance}: hiding ${option.label} left ${dangling.length} dangling relation(s)`
        );
      }
    }

    const graph = layoutGraphNodes(person, visible, lookup);
    const anchorPositions = new Map(
      graph.nodes
        .filter((node) => node.isProcessAnchor)
        .map((node) => [node.id, { x: node.x, y: node.y }])
    );
    settleClassPhysicsSync(graph.nodes, graph.edges, graph.focusNode);
    const labels = graph.nodes.map((n) => n.label).sort();
    const overlaps = countOverlaps(graph.nodes);
    counts.set(`${tag}\0${distance}`, labels.length);

    // Relations merged for the sources view must not double-draw existing edges.
    const uniqueEdges = new Set(
      graph.edges.map((e) => `${e.a.id}\0${e.b.id}\0${e.predicateLabel}`)
    );
    if (uniqueEdges.size !== graph.edges.length) {
      fail(
        `${tag} d=${distance}: ${graph.edges.length - uniqueEdges.size} duplicate edges ` +
          `(${graph.edges.length} edges, ${uniqueEdges.size} unique)`
      );
    }

    const rule = expected[distance];
    for (const name of rule.mustExclude || []) {
      if (labels.includes(name)) fail(`${tag} d=${distance}: should not include ${name}`);
    }
    for (const name of rule.mustInclude || []) {
      if (!labels.includes(name)) fail(`${tag} d=${distance}: should include ${name}`);
    }
    if (labels.length < rule.min) {
      fail(`${tag} d=${distance}: expected at least ${rule.min} nodes, got ${labels.length}`);
    }
    for (const name of LEDGER_LABELS) {
      const present = labels.includes(name);
      const wanted = showSources && LEDGER_EXPECTED_AT[distance].includes(name);
      if (wanted && !present) fail(`${tag} d=${distance}: should include ${name}`);
      if (!wanted && present) fail(`${tag} d=${distance}: should not include ${name}`);
    }
    if (overlaps !== 0) fail(`${tag} d=${distance}: ${overlaps} overlaps`);
    if (graph.focusNode.x !== 0 || graph.focusNode.y !== 0) {
      fail(`${tag} d=${distance}: focus node is not centered`);
    }
    for (const node of graph.nodes) {
      if (node.id === graph.focusNode.id) continue;
      if (node.isProcessAnchor) {
        const initial = anchorPositions.get(node.id);
        if (node.physicsEnabled || node.x !== initial.x || node.y !== initial.y) {
          fail(`${tag} d=${distance}: process anchor ${node.label} moved`);
        }
        if (Math.hypot(node.x, node.y) + 0.01 < PROCESS_ROOT_RADIUS) {
          fail(`${tag} d=${distance}: process anchor ${node.label} is too close to focus`);
        }
      } else if (!node.physicsEnabled) {
        fail(`${tag} d=${distance}: class ${node.label} does not have physics enabled`);
      }
    }

    const rayNodes = graph.nodes.filter((node) => node.id !== graph.focusNode.id);
    const unassigned = rayNodes.filter((node) => !node.rayId || !node.radialLevel);
    if (unassigned.length > 0) {
      fail(`${tag} d=${distance}: ${unassigned.length} nodes are not assigned to a process ray`);
    }

    const levelCountsByRay = new Map();
    for (const node of rayNodes) {
      const key = `${node.rayId}\0${node.radialLevel}`;
      levelCountsByRay.set(key, (levelCountsByRay.get(key) || 0) + 1);
    }
    for (const [key, count] of levelCountsByRay.entries()) {
      const level = Number(key.slice(key.lastIndexOf("\0") + 1));
      const capacity = level === 1 ? 1 : 2 ** (level - 1);
      if (count > capacity) {
        fail(`${tag} d=${distance}: ray level ${level} uses ${count}/${capacity} positions`);
      }
    }
    console.log(
      `${tag} d=${distance} nodes=${labels.length} edges=${graph.edges.length} ` +
        `overlaps=${overlaps}: ${labels.join(", ")}`
    );
  }

  const at = (d) => counts.get(`${tag}\0${d}`);
  if (at(1) >= at(2) || at(2) >= at(3)) {
    fail(`${tag}: node count should grow with distance`);
  }

  // A larger distance only ever adds classes to the filter list.
  for (const [smaller, larger] of [
    [1, 2],
    [2, 3],
  ]) {
    const missing = [...optionLabelsByDistance.get(smaller)].filter(
      (label) => !optionLabelsByDistance.get(larger).has(label)
    );
    if (missing.length > 0) {
      fail(`${tag}: d=${larger} class list dropped ${missing.join(", ")} present at d=${smaller}`);
    }
  }
}

// The per-class cap keeps the most recent processes and drops the rest.
{
  const synthetic = Array.from({ length: 14 }, (_, i) => ({
    id: `p${i}`,
    bfoBucket: "Process",
    classLabel: "Synthetic",
    startedAt: `20${String(10 + i).padStart(2, "0")}-01-01`,
  }));
  const suppressed = suppressOldProcesses(synthetic);
  if (suppressed.size !== 14 - MAX_PROCESSES_PER_CLASS) {
    fail(`cap: suppressed ${suppressed.size}, expected ${14 - MAX_PROCESSES_PER_CLASS}`);
  }
  const kept = synthetic.filter((r) => !suppressed.has(r.id)).map((r) => r.startedAt);
  const newest = [...synthetic]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, MAX_PROCESSES_PER_CLASS)
    .map((r) => r.startedAt);
  if ([...kept].sort().join() !== [...newest].sort().join()) {
    fail(`cap: kept the wrong processes (${kept.join(", ")})`);
  }
  // Classes at or under the cap are untouched.
  if (suppressOldProcesses(synthetic.slice(0, MAX_PROCESSES_PER_CLASS)).size !== 0) {
    fail("cap: suppressed processes in a class that is under the cap");
  }
}

// Toggling ledger sources on never removes nodes, and reveals provenance wherever the ledger
// layer is within reach of the selected distance.
for (const distance of [1, 2, 3]) {
  const off = counts.get(`sources=off\0${distance}`);
  const on = counts.get(`sources=on\0${distance}`);
  const shouldGrow = LEDGER_EXPECTED_AT[distance].length > 0;
  if (on < off) {
    fail(`d=${distance}: ledger sources should never drop nodes (off=${off}, on=${on})`);
  }
  if (shouldGrow && !(on > off)) {
    fail(`d=${distance}: ledger sources should add nodes (off=${off}, on=${on})`);
  }
  if (!shouldGrow && on !== off) {
    fail(`d=${distance}: no ledger node is in reach, so counts should match (off=${off}, on=${on})`);
  }
}

process.exit(failed ? 1 : 0);
