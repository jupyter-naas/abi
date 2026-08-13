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
  1: { min: 14, mustExclude: ["Alice Dupont", "Christine Example", "Pascal Example"] },
  2: { min: 15, mustInclude: ["Alice Dupont"], mustExclude: ["Christine Example", "Pascal Example"] },
  3: { min: 25, mustInclude: ["Alice Dupont", "Christine Example", "Pascal Example"] },
};

let failed = false;
const prev = new Map();

for (const distance of [1, 2, 3]) {
  const visible = collectVisibleGraph(adj, personId, distance, false);
  const graph = layoutGraphNodes(person, visible, lookup, { physics: true });
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
  console.log(`d=${distance} nodes=${labels.length} overlaps=${overlaps}: ${labels.join(", ")}`);
}

if (prev.get(1) >= prev.get(2) || prev.get(2) >= prev.get(3)) {
  console.log("FAIL: node count should grow with distance");
  failed = true;
}

process.exit(failed ? 1 : 0);
