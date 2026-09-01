import { describe, expect, it } from 'vitest';
import {
  computeSlidesPreviewScale,
  prepareSlidesPreviewHtml,
  SLIDES_PREVIEW_BRIDGE_SCRIPT_ID,
  SLIDES_PREVIEW_FIT_STYLE_ID,
  SLIDES_PREVIEW_MESSAGE_SOURCE,
  SLIDES_STAGE_HEIGHT,
  SLIDES_STAGE_WIDTH,
} from './slides-preview-fit';
import { SLIDES_PPTX_FROM_DOM_SCRIPT_ID } from './slides-pptx-from-dom';

describe('computeSlidesPreviewScale', () => {
  it('contains a 16:9 stage in a wide pane (letterbox top/bottom)', () => {
    const scale = computeSlidesPreviewScale(1600, 600);
    expect(scale).toBeCloseTo(600 / SLIDES_STAGE_HEIGHT, 5);
  });

  it('contains a 16:9 stage in a tall pane (pillarbox left/right)', () => {
    const scale = computeSlidesPreviewScale(800, 900);
    expect(scale).toBeCloseTo(800 / SLIDES_STAGE_WIDTH, 5);
  });

  it('returns 1 for non-positive inputs', () => {
    expect(computeSlidesPreviewScale(0, 720)).toBe(1);
    expect(computeSlidesPreviewScale(1280, -1)).toBe(1);
  });
});

describe('prepareSlidesPreviewHtml', () => {
  it('injects fit CSS and postMessage bridge once', () => {
    const src = '<!doctype html><html><head><title>t</title></head><body><main class="deck"></main></body></html>';
    const once = prepareSlidesPreviewHtml(src);
    expect(once).toContain(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`);
    expect(once).toContain(`id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}"`);
    expect(once).toContain(`id="${SLIDES_PPTX_FROM_DOM_SCRIPT_ID}"`);
    expect(once).toContain('window.buildPptx = buildPptx');
    expect(once).toContain(SLIDES_PREVIEW_MESSAGE_SOURCE);
    expect(once).toContain(`${SLIDES_STAGE_WIDTH}px`);
    expect(once).toContain('deck-menubar');
    const twice = prepareSlidesPreviewHtml(once);
    expect(twice).toBe(once);
  });

  it('overrides a hardcoded seed buildPptx with the DOM walker', () => {
    const src =
      '<!doctype html><html><head></head><body><main class="deck"></main>' +
      '<script>async function buildPptx(){ /* [["1","Context"],["2","Approach"]] */ }</script>' +
      '</body></html>';
    const out = prepareSlidesPreviewHtml(src);
    const walkerAt = out.lastIndexOf('window.buildPptx = buildPptx');
    const seedAt = out.indexOf('[["1","Context"],["2","Approach"]]');
    expect(walkerAt).toBeGreaterThan(seedAt);
    expect(out).toContain(SLIDES_PPTX_FROM_DOM_SCRIPT_ID);
  });

  it('prefixes when head is missing', () => {
    const src = '<main class="deck"><section class="slide"></section></main>';
    const out = prepareSlidesPreviewHtml(src);
    expect(out.startsWith(`<style id="${SLIDES_PREVIEW_FIT_STYLE_ID}">`)).toBe(true);
    expect(out).toContain(`id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}"`);
  });
});
