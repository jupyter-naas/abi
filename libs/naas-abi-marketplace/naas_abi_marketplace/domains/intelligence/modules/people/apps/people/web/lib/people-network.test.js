import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { layoutNetwork, organizationSize } from "./people-network.js";

const nodes = [
  { id: "person:a", kind: "person" },
  { id: "person:b", kind: "person" },
  { id: "person:c", kind: "person" },
  { id: "organization:firm", kind: "organization" },
];
const edges = [
  { source: "person:a", target: "organization:firm" },
  { source: "person:b", target: "organization:firm" },
];

describe("layoutNetwork", () => {
  it("places every node at a finite point", () => {
    const positions = layoutNetwork(nodes, edges);
    assert.deepEqual(Object.keys(positions).sort(), nodes.map((n) => n.id).sort());
    for (const { x, y } of Object.values(positions)) {
      assert.ok(Number.isFinite(x) && Number.isFinite(y));
    }
  });

  it("is deterministic", () => {
    assert.deepEqual(layoutNetwork(nodes, edges), layoutNetwork(nodes, edges));
  });

  it("pulls tied nodes closer than an untied one", () => {
    const p = layoutNetwork(nodes, edges);
    const distance = (u, v) => Math.hypot(p[u].x - p[v].x, p[u].y - p[v].y);
    assert.ok(distance("person:a", "organization:firm") < distance("person:c", "organization:firm"));
  });

  it("ignores edges to nodes it was not given", () => {
    const positions = layoutNetwork(nodes, [...edges, { source: "person:a", target: "nowhere" }]);
    assert.equal(Object.keys(positions).length, nodes.length);
  });

  it("returns nothing for nothing", () => {
    assert.deepEqual(layoutNetwork([], []), {});
  });
});

describe("organizationSize", () => {
  it("grows with the people an organization ties, up to a cap", () => {
    assert.ok(organizationSize(2) < organizationSize(10));
    assert.equal(organizationSize(10_000), 56);
  });
});
