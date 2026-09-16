export type LayoutBox = { id: string; width: number; height: number; primary?: boolean; group?: string; label?: string };
export type LayoutLink = { source: string; target: string };
export type Position = { x: number; y: number };

/** A stable, compact arrangement measured from card edges rather than a fixed-radius scatter. */
export function compactNetworkPositions(boxes: LayoutBox[], links: LayoutLink[], gap = 40): Map<string, Position> {
  if (!boxes.length) return new Map();
  gap = Number.isFinite(gap) ? Math.max(36, gap) : 40; // Room for both 18px connector stubs.
  const byId = new Map(boxes.map(box => [box.id, box]));
  const neighbours = new Map(boxes.map(box => [box.id, new Set<string>()]));
  for (const link of links) if (link.source !== link.target && byId.has(link.source) && byId.has(link.target)) {
    neighbours.get(link.source)!.add(link.target); neighbours.get(link.target)!.add(link.source);
  }
  const compare = (a: string, b: string) => (byId.get(a)!.group || '').localeCompare(byId.get(b)!.group || '')
    || (byId.get(a)!.label || a).localeCompare(byId.get(b)!.label || b) || a.localeCompare(b);
  const roots = [...byId.keys()].sort((a, b) => Number(Boolean(byId.get(b)!.primary)) - Number(Boolean(byId.get(a)!.primary))
    || neighbours.get(b)!.size - neighbours.get(a)!.size || compare(a, b));
  // Explore the selected term first. Its neighbours occupy the nearest cells;
  // disconnected components follow without inventing relationships between them.
  const order: string[] = [], seen = new Set<string>();
  for (const root of roots) {
    if (seen.has(root)) continue;
    const queue = [root]; seen.add(root);
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i]; order.push(id);
      for (const next of [...neighbours.get(id)!].sort(compare)) if (!seen.has(next)) { seen.add(next); queue.push(next); }
    }
  }
  const width = Math.max(...boxes.map(box => box.width)), height = Math.max(...boxes.map(box => box.height));
  // Choose a balanced rectangle, including real card dimensions and the gaps.
  let columns = 1, score = Infinity;
  for (let count = 1; count <= boxes.length; count++) {
    const rows = Math.ceil(boxes.length / count);
    const w = count * width + (count - 1) * gap, h = rows * height + (rows - 1) * gap;
    const candidate = Math.abs(Math.log(w / h / 1.6)) + (count * rows - boxes.length) / boxes.length;
    if (candidate < score) { score = candidate; columns = count; }
  }
  const rows = Math.ceil(boxes.length / columns);
  const cells = Array.from({length: rows * columns}, (_, i) => ({ x: i % columns - (columns - 1) / 2, y: Math.floor(i / columns) - (rows - 1) / 2 }));
  cells.sort((a, b) => Math.hypot(a.x, a.y) - Math.hypot(b.x, b.y) || a.y - b.y || a.x - b.x);
  const positions = new Map<string, Position>();
  const available = [...cells];
  for (const id of order) {
    const placed = [...neighbours.get(id)!].flatMap(neighbour => positions.has(neighbour) ? [positions.get(neighbour)!] : []);
    // Minimize distance to already placed neighbours, with a stable tie break.
    let best = 0, bestDistance = Infinity;
    available.forEach((cell, index) => {
      const x = cell.x * (width + gap), y = cell.y * (height + gap);
      const distance = placed.length ? placed.reduce((sum, p) => sum + Math.abs(x - p.x) + Math.abs(y - p.y), 0) / placed.length : Math.hypot(x, y);
      if (distance < bestDistance) { best = index; bestDistance = distance; }
    });
    const [cell] = available.splice(best, 1);
    positions.set(id, {x: cell.x * (width + gap), y: cell.y * (height + gap)});
  }
  return positions;
}
