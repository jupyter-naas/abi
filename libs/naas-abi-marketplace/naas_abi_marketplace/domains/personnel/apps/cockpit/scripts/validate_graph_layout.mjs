import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const cockpitRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const graphModule = pathToFileURL(path.join(cockpitRoot, "web/js/graph.js")).href;
const dataPath = path.join(cockpitRoot, "web/data/entities/_demo/graph/index.json");

const {
  buildGraphIndex,
  collectVisibleGraph,
  layoutGraphNodes,
  countOverlaps,
  settleClassPhysicsSync,
  PROCESS_ROOT_RADIUS,
} = await import(graphModule);

const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const adj = buildGraphIndex(data);
adj.ledgerProcesses = data.ledgerProcesses || [];
adj.allRelations = data.allRelations || data.relations || [];

const lookup = {
  peopleById: adj.peopleById,
  processesById: adj.processesById,
  entitiesById: adj.entitiesById,
  birthHubByPerson: adj.birthHubByPerson,
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

let failed = false;
const prev = new Map();

for (const distance of [1, 2, 3]) {
  const visible = collectVisibleGraph(adj, personId, distance, false);
  const graph = layoutGraphNodes(person, visible, lookup);
  const anchorPositions = new Map(
    graph.nodes
      .filter((node) => node.isProcessAnchor)
      .map((node) => [node.id, { x: node.x, y: node.y }])
  );
  settleClassPhysicsSync(graph.nodes, graph.edges, graph.focusNode);
  const labels = graph.nodes.map((n) => n.label).sort();
  const overlaps = countOverlaps(graph.nodes);
  prev.set(distance, labels.length);

  const rule = expected[distance];
  for (const name of rule.mustExclude || []) {
    if (labels.includes(name)) {
      console.log(`FAIL d=${distance}: should not include ${name}`);
      failed = true;
    }
  }
  for (const name of rule.mustInclude || []) {
    if (!labels.includes(name)) {
      console.log(`FAIL d=${distance}: should include ${name}`);
      failed = true;
    }
  }
  if (labels.length < rule.min) {
    console.log(`FAIL d=${distance}: expected at least ${rule.min} nodes, got ${labels.length}`);
    failed = true;
  }
  if (overlaps !== 0) {
    console.log(`FAIL d=${distance}: ${overlaps} overlaps`);
    failed = true;
  }
  if (graph.focusNode.x !== 0 || graph.focusNode.y !== 0) {
    console.log(`FAIL d=${distance}: focus node is not centered`);
    failed = true;
  }
  for (const node of graph.nodes) {
    if (node.id === graph.focusNode.id) continue;
    if (node.isProcessAnchor) {
      const initial = anchorPositions.get(node.id);
      if (node.physicsEnabled || node.x !== initial.x || node.y !== initial.y) {
        console.log(`FAIL d=${distance}: process anchor ${node.label} moved`);
        failed = true;
      }
      if (Math.hypot(node.x, node.y) + 0.01 < PROCESS_ROOT_RADIUS) {
        console.log(`FAIL d=${distance}: process anchor ${node.label} is too close to focus`);
        failed = true;
      }
    } else if (!node.physicsEnabled) {
      console.log(`FAIL d=${distance}: class ${node.label} does not have physics enabled`);
      failed = true;
    }
  }

  const rayNodes = graph.nodes.filter((node) => node.id !== graph.focusNode.id);
  const unassigned = rayNodes.filter((node) => !node.rayId || !node.radialLevel);
  if (unassigned.length > 0) {
    console.log(`FAIL d=${distance}: ${unassigned.length} nodes are not assigned to a process ray`);
    failed = true;
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
      console.log(`FAIL d=${distance}: ray level ${level} uses ${count}/${capacity} positions`);
      failed = true;
    }
  }
  console.log(`d=${distance} nodes=${labels.length} overlaps=${overlaps}: ${labels.join(", ")}`);
}

if (prev.get(1) >= prev.get(2) || prev.get(2) >= prev.get(3)) {
  console.log("FAIL: node count should grow with distance");
  failed = true;
}

process.exit(failed ? 1 : 0);
