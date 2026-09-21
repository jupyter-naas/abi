/**
 * Which side of a card a connector leaves and enters by, in the BFO zone layout,
 * decided by the pair of BFO buckets it joins. This is the only place the table
 * is written down: the layout sizes its margins and corridors from what
 * ``sidesFor`` says, and the router routes to it, without knowing the table.
 *
 * Layout: the top band is Process | Temporal Region; the bottom band is
 * Material Entity | Site | GDC | Quality | Realizable. N/S/W/E are the top,
 * bottom, left and right border of a card.
 *
 * A rule applies to the pair of buckets whichever way the connector runs, and
 * to every family of relation (subClassOf, restriction, object property).
 * A pair with no rule is free: the router picks any side, as it does for the
 * tree layouts.
 */

export const OTHER = "Other";
const KNOWN = new Set(["Process", "Temporal Region", "Material Entity", "Site", "GDC", "Quality", "Realizable"]);

/** A bucket the zones do not have a place for is "Other", like the layout does. */
export const bucketKey = (bucket) => (KNOWN.has(bucket) ? bucket : OTHER);

/**
 * Each row: the two buckets, and the side of each one's card, in that order.
 *
 *  1. U over the top                          Process / Temporal Region   N / N
 *  2. east out of Process, west into Quality  Process / Quality, Realizable  E / W
 *  3. south out of Process, west into GDC     Process / GDC               S / W
 *  4. west out of Process, top of Site        Process / Site              W / N
 *  5. C down the left margin                  Process / Material Entity   W / W
 *  6. U under the bottom band                 the pairs below             S / S
 */
export const BFO_EDGE_RULES = [
  { buckets: ["Process", "Temporal Region"], sides: ["N", "N"] },
  { buckets: ["Process", "Quality"], sides: ["E", "W"] },
  { buckets: ["Process", "Realizable"], sides: ["E", "W"] },
  { buckets: ["Process", "GDC"], sides: ["S", "W"] },
  { buckets: ["Process", "Site"], sides: ["W", "N"] },
  { buckets: ["Process", "Material Entity"], sides: ["W", "W"] },
  { buckets: ["Material Entity", "GDC"], sides: ["S", "S"] },
  { buckets: ["Material Entity", "Quality"], sides: ["S", "S"] },
  { buckets: ["Material Entity", "Realizable"], sides: ["S", "S"] },
  { buckets: ["GDC", "Realizable"], sides: ["S", "S"] },
  { buckets: ["Site", "GDC"], sides: ["S", "S"] },
  { buckets: ["Site", "Quality"], sides: ["S", "S"] },
  { buckets: ["Site", "Realizable"], sides: ["S", "S"] },
];
// Free, by absence: a bucket with itself; Material Entity / Site; GDC / Quality;
// Quality / Realizable; Temporal Region with anything but Process; and Other.

/**
 * The sides allowed at each end of a connector from a card in ``bucketA`` to a
 * card in ``bucketB``: ``{ a: [side], b: [side] }``, or null when the pair is
 * free. Either order gives the same rule.
 */
export function sidesFor(bucketA, bucketB) {
  const a = bucketKey(bucketA);
  const b = bucketKey(bucketB);
  if (a === b) return null;
  for (const rule of BFO_EDGE_RULES) {
    const [first, second] = rule.buckets;
    if (a === first && b === second) return { a: [rule.sides[0]], b: [rule.sides[1]] };
    if (a === second && b === first) return { a: [rule.sides[1]], b: [rule.sides[0]] };
  }
  return null;
}

/**
 * ``sidesFor`` for a connector: the sides at its source and at its target,
 * given each card's bucket. ``bucketOf`` maps a card id to its bucket.
 */
export function edgeSides(bucketOf) {
  return (edge) => {
    const rule = sidesFor(bucketOf(edge.source), bucketOf(edge.target));
    return rule ? { source: rule.a, target: rule.b } : null;
  };
}

/**
 * How many connectors end on each side of each card: ``Map id -> {N, S, E, W,
 * free}``. A connector whose sides are fixed counts on its side; the rest are
 * ``free``, wherever the router puts them. ``sidesOf`` is ``edgeSides(...)``, or
 * absent when every connector is free.
 */
export function sideLoads(edges, sidesOf) {
  const loads = new Map();
  const load = (id) => {
    if (!loads.has(id)) loads.set(id, { N: 0, S: 0, E: 0, W: 0, free: 0 });
    return loads.get(id);
  };
  for (const edge of edges) {
    const rule = sidesOf?.(edge);
    for (const [end, id] of [["source", edge.source], ["target", edge.target]]) {
      const sides = rule?.[end];
      if (sides?.length === 1) load(id)[sides[0]] += 1;
      else load(id).free += 1;
    }
  }
  return loads;
}
