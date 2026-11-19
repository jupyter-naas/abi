import { describe, expect, it } from 'vitest';
import { architecture, componentPosition, focusDistance, PLANE_DEPTH, PLANE_WIDTH } from './architecture-model';

describe('ABI camera framing', () => {
  for (const [width, height] of [[1400, 650], [500, 650], [300, 450], [900, 300]]) {
    for (const expanded of [false, true]) {
      it(`fits the complete ${expanded ? 'expanded' : 'normal'} plane at ${width}×${height}`, () => {
        const distance = focusDistance(width, height, expanded);
        const visibleDepth = (distance - 1) * 2 * Math.tan(Math.PI / 9);
        const scale = expanded ? 1.2 : 1;
        expect(visibleDepth).toBeGreaterThan(PLANE_DEPTH * scale);
        expect(visibleDepth * width / height).toBeGreaterThan(PLANE_WIDTH * scale);
      });
    }
  }
  it('keeps all source components inside their plane', () => {
    for (const layer of architecture.layers) {
      const components = architecture.components.filter(c => c.layer === layer.id);
      components.forEach((_, i) => {
        const p = componentPosition(i, components.length, false);
        expect(Math.abs(p.x) + 3.35 / 2).toBeLessThan(PLANE_WIDTH / 2);
        expect(Math.abs(p.z) + 1.5 / 2).toBeLessThan(PLANE_DEPTH / 2);
      });
    }
  });
  it('has valid directed dependency endpoints and no self links', () => {
    const ids = new Set(architecture.components.map(c => c.id));
    for (const edge of architecture.edges) {
      expect(ids.has(edge.source) && ids.has(edge.target)).toBe(true);
      expect(edge.source).not.toBe(edge.target);
      expect(edge.count).toBeGreaterThan(0);
    }
  });
});
