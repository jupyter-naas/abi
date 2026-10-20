/** What the ontology page draws: run with ``node --test web/lib/`` from apps/people. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { connectedNodes, filterGraph } from "./ontology-graph.js";

const node = (id, bucket = "Process") => ({ id, label: id, bucket });
const edge = (source, target, relation) => ({ id: `${source}-${target}-${relation}`, source, target, label: "", relation });

// A process slice: the role is a subclass of abi:Role and restricted to the act.
const graph = {
  nodes: [node("act"), node("person", "Material Entity"), node("candidate", "Realizable"), node("Role", "Realizable")],
  edges: [
    edge("act", "person", "restriction"),
    edge("candidate", "act", "restriction"),
    edge("candidate", "Role", "hierarchy"),
    edge("act", "candidate", "property"),
  ],
};
const only = (family) => ({ hierarchy: false, restrictions: false, properties: false, [family]: true });
const ids = (view) => view.nodes.map((n) => n.id).sort();

test("a class linked only by a family that is off is not drawn", () => {
  assert.deepEqual(ids(filterGraph(graph, only("restrictions"))), ["act", "candidate", "person"]);
});

test("each family brings its own classes back", () => {
  assert.deepEqual(ids(filterGraph(graph, only("hierarchy"))), ["Role", "candidate"]);
  assert.deepEqual(ids(filterGraph(graph, only("properties"))), ["act", "candidate"]);
  assert.deepEqual(ids(filterGraph(graph, { hierarchy: true, restrictions: true, properties: true })), ["Role", "act", "candidate", "person"]);
});

test("with every family off nothing is drawn", () => {
  const view = filterGraph(graph, { hierarchy: false, restrictions: false, properties: false });
  assert.deepEqual(view, { nodes: [], edges: [] });
});

test("a bucket or a hidden class does not change which classes are connected", () => {
  const all = { hierarchy: true, restrictions: true, properties: true };
  // Only Realizable: the roles are connected, to the act and the person, so they are drawn, without those connections.
  const view = filterGraph(graph, all, new Set(["Realizable"]));
  assert.deepEqual(ids(view), ["Role", "candidate"]);
  assert.deepEqual(view.edges.map((e) => e.relation), ["hierarchy"]);
  // Hide the act by hand: the person is still connected in the ontology, so it stays.
  assert.deepEqual(ids(filterGraph(graph, all, new Set(), new Set(["act"]))), ["Role", "candidate", "person"]);
});

test("a file's classes are connected only by what it names", () => {
  // Only Role and candidate in the file, restrictions only: their one link is the hierarchy.
  const file = new Set(["Role", "candidate"]);
  assert.deepEqual(filterGraph(graph, only("restrictions"), new Set(), new Set(), file), { nodes: [], edges: [] });
  assert.deepEqual(ids(filterGraph(graph, only("hierarchy"), new Set(), new Set(), file)), ["Role", "candidate"]);
});

test("the bucket panel counts what is drawn out of what is connected", () => {
  const families = only("restrictions");
  const listed = connectedNodes(graph, families).filter((n) => n.bucket === "Realizable");
  assert.deepEqual(listed.map((n) => n.id), ["candidate"]); // Role is not connected by a restriction
  const drawn = new Set(filterGraph(graph, families, new Set(), new Set(["candidate"])).nodes.map((n) => n.id));
  assert.equal(listed.filter((n) => drawn.has(n.id)).length, 0);
  assert.equal(listed.filter((n) => new Set(filterGraph(graph, families).nodes.map((m) => m.id)).has(n.id)).length, 1);
});
