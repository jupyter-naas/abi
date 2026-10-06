import type { Network } from 'vis-network/standalone';

type Point = { x: number; y: number };
export type Viewport = { scale: number; position: Point };

/** Keep the nearest visible term under the same screen position as spacing changes. */
export function spacingViewport(
  viewport: Viewport,
  before: Record<string, Point>,
  after: Array<{ id?: string | number; x?: number; y?: number }>,
): Viewport {
  let distance = Infinity;
  let position = viewport.position;
  for (const node of after) {
    if (node.id === undefined || node.x === undefined || node.y === undefined) continue;
    const old = before[node.id];
    if (!old) continue;
    const delta = Math.hypot(old.x - viewport.position.x, old.y - viewport.position.y);
    if (delta < distance) {
      distance = delta;
      position = { x: viewport.position.x + node.x - old.x, y: viewport.position.y + node.y - old.y };
    }
  }
  return { scale: viewport.scale, position };
}

/** Automatic framing may crop a large graph to retain readable labels. Manual Fit stays native. */
export function fitReadableViewport(
  network: Pick<Network, 'fit' | 'moveTo' | 'getScale' | 'getViewPosition'>,
  minimumScale: number,
  duration: number,
) {
  const animation = { duration, easingFunction: 'easeInOutQuad' as const };
  if (minimumScale <= 0) { network.fit({ animation }); return; }
  const previous = { scale: network.getScale(), position: network.getViewPosition() };
  network.fit({ animation: false });
  const target = { scale: Math.max(minimumScale, network.getScale()), position: network.getViewPosition() };
  network.moveTo({ ...previous, animation: false });
  network.moveTo({ ...target, animation });
}

/** Frame a canvas rectangle (e.g. drawn BFO zones), not just the nodes, under the same readable minimum. */
export function fitBoundsViewport(
  network: Pick<Network, 'moveTo'>,
  bounds: { x: number; y: number; width: number; height: number },
  viewport: { width: number; height: number },
  minimumScale: number,
  duration: number,
) {
  if (bounds.width <= 0 || bounds.height <= 0 || viewport.width <= 0 || viewport.height <= 0) return;
  const fit = Math.min(viewport.width / bounds.width, viewport.height / bounds.height) * 0.96;
  network.moveTo({
    scale: Math.max(minimumScale, fit),
    position: { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 },
    animation: duration > 0 ? { duration, easingFunction: 'easeInOutQuad' } : false,
  });
}
