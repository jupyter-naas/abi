import { describe, expect, it } from 'vitest';
import {
  computeSlidesPreviewScale,
  slidesPreviewIndexFromScroll,
  slidesPreviewScrollTop,
  coverHeroCss,
  deckBufferHasCover,
  extractFirstSlideHtml,
  extractSlideHtmlAt,
  prepareSlidesCoverHtml,
  prepareSlidesPreviewHtml,
  readDeckCoverHtml,
  SLIDES_COVER_FIT_STYLE_ID,
  SLIDES_INDUSTRY_STAGE_SCALE,
  SLIDES_PDF_EXPORT_ACK_MS,
  SLIDES_PREVIEW_BRIDGE_SCRIPT_ID,
  SLIDES_PREVIEW_FIT_STYLE_ID,
  SLIDES_PREVIEW_MESSAGE_SOURCE,
  SLIDES_PREVIEW_PRINT_CSS,
  SLIDES_PRINT_PAGE_HEIGHT_IN,
  SLIDES_PRINT_PAGE_WIDTH_IN,
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

describe('slidesPreviewScrollTop', () => {
  it('maps a selected index to host scroll at the current scale', () => {
    expect(slidesPreviewScrollTop(0, 0.5)).toBe(0);
    expect(slidesPreviewScrollTop(2, 0.5)).toBe(2 * SLIDES_STAGE_HEIGHT * 0.5);
    expect(slidesPreviewIndexFromScroll(SLIDES_STAGE_HEIGHT * 0.5, 0.5)).toBe(1);
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
    expect(once).toContain('export-pdf');
    expect(once).toContain('window.print');
    expect(once).toContain('@media print');
    expect(once).toContain(`size: ${SLIDES_PRINT_PAGE_WIDTH_IN} ${SLIDES_PRINT_PAGE_HEIGHT_IN}; margin: 0;`);
    expect(once).not.toMatch(/@page \{[^}]*landscape/);
    expect(once).toContain('display: block !important');
    expect(once).toContain('.slide-index');
    expect(once).toContain('.industry-stage');
    expect(once).toContain(`zoom: ${SLIDES_INDUSTRY_STAGE_SCALE}`);
    expect(once).toContain('print-color-adjust: exact');
    expect(once).toContain('page-break-after: always');
    expect(once).toContain('page-break-before: always');
    expect(once).toContain('contain: strict');
    expect(once).toContain('beforeprint');
    const ackAt = once.indexOf("type: 'export-pdf-result', ok: true");
    const printAt = once.lastIndexOf('window.print()');
    const timeoutAt = once.indexOf('setTimeout(function ()');
    expect(ackAt).toBeGreaterThan(-1);
    expect(printAt).toBeGreaterThan(ackAt);
    expect(timeoutAt).toBeGreaterThan(ackAt);
    expect(timeoutAt).toBeLessThan(printAt);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('@media print');
    expect(SLIDES_PDF_EXPORT_ACK_MS).toBeGreaterThan(0);
    const twice = prepareSlidesPreviewHtml(once);
    expect(twice).toBe(once);
  });

  it('waits for every <img> before posting images-ready', () => {
    const src = '<!doctype html><html><head></head><body><main class="deck"></main></body></html>';
    const out = prepareSlidesPreviewHtml(src);
    expect(out).toContain('waitForImages');
    expect(out).toContain("type: 'images-ready'");
    const onReadyAt = out.indexOf('function onReady()');
    const waitForImagesCallAt = out.indexOf('waitForImages().then');
    expect(waitForImagesCallAt).toBeGreaterThan(onReadyAt);
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

const TWO_SLIDE_DECK = `<!doctype html><html><head>
<title>Deck</title>
<style>.slide { background: #fff; }</style>
<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js"></script>
</head><body>
<main class="deck">
<section id="slide-cover" class="slide cover"><h1>Cover Title</h1></section>
<section class="slide"><h1>Agenda</h1></section>
</main>
<script>const IMG = { hero: "data:image/svg+xml,hero" };</script>
</body></html>`;

describe('SLIDES_PREVIEW_PRINT_CSS', () => {
  it('sizes the page and each slide in the same inches, without landscape', () => {
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain(
      `@page { size: ${SLIDES_PRINT_PAGE_WIDTH_IN} ${SLIDES_PRINT_PAGE_HEIGHT_IN}; margin: 0; }`,
    );
    expect(SLIDES_PREVIEW_PRINT_CSS).not.toMatch(/@page \{[^}]*landscape/);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain(`width: ${SLIDES_PRINT_PAGE_WIDTH_IN} !important`);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain(`height: ${SLIDES_PRINT_PAGE_HEIGHT_IN} !important`);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('max-width: none !important');
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('max-height: none !important');
  });

  it('uses zoom for the industry paint box so print layout is 1280x720', () => {
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain(`zoom: ${SLIDES_INDUSTRY_STAGE_SCALE} !important`);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('transform: none !important');
    expect(SLIDES_PREVIEW_PRINT_CSS).not.toContain(
      `transform: scale(${SLIDES_INDUSTRY_STAGE_SCALE})`,
    );
  });
});

describe('prepareSlidesCoverHtml', () => {
  it('keeps the first slide and drops the rest', () => {
    const cover = prepareSlidesCoverHtml(TWO_SLIDE_DECK);
    expect(cover).toContain('Cover Title');
    expect(cover).toContain('id="slide-cover"');
    expect(cover).not.toContain('Agenda');
    expect(cover).toContain(`id="${SLIDES_COVER_FIT_STYLE_ID}"`);
    expect(cover).toContain('.industry-stage');
    expect(cover).toContain(`transform: scale(${SLIDES_INDUSTRY_STAGE_SCALE})`);
    expect(cover).not.toContain('pptxgen');
    expect(cover).not.toContain('export-pdf');
  });

  it('returns null when no slide section exists', () => {
    expect(prepareSlidesCoverHtml('<html><body>no slides</body></html>')).toBeNull();
  });

  it('builds a filmstrip thumb for a later slide', () => {
    const thumb = prepareSlidesCoverHtml(TWO_SLIDE_DECK, 1);
    expect(thumb).toContain('Agenda');
    expect(thumb).not.toContain('Cover Title');
    expect(thumb).toContain(`id="${SLIDES_COVER_FIT_STYLE_ID}"`);
  });

  it('reads a small hero data URL for the cover band', () => {
    expect(coverHeroCss(TWO_SLIDE_DECK)).toContain('data:image/svg+xml,hero');
  });

  it('allows a relative assets/ hero after seed extraction', () => {
    const html = 'const IMG = { hero: "assets/img-001.jpg" };';
    expect(coverHeroCss(html)).toContain('url("assets/img-001.jpg")');
  });
});

describe('deckBufferHasCover', () => {
  it('waits for a complete first slide', () => {
    expect(deckBufferHasCover('<head></head><section class="slide"><h1>x')).toBe(false);
    expect(deckBufferHasCover(TWO_SLIDE_DECK)).toBe(true);
  });
});

describe('extractFirstSlideHtml', () => {
  it('skips a section that is not a slide', () => {
    const html =
      '<section class="notes">skip</section><section class="slide cover"><h1>Keep</h1></section>';
    expect(extractFirstSlideHtml(html)).toContain('Keep');
    expect(extractFirstSlideHtml(html)).not.toContain('skip');
  });
});

describe('extractSlideHtmlAt', () => {
  it('returns the slide at the filmstrip index', () => {
    expect(extractSlideHtmlAt(TWO_SLIDE_DECK, 0)).toContain('Cover Title');
    expect(extractSlideHtmlAt(TWO_SLIDE_DECK, 1)).toContain('Agenda');
    expect(extractSlideHtmlAt(TWO_SLIDE_DECK, 1)).not.toContain('Cover Title');
    expect(extractSlideHtmlAt(TWO_SLIDE_DECK, 2)).toBeNull();
    expect(extractSlideHtmlAt('', 0)).toBeNull();
  });
});

describe('readDeckCoverHtml', () => {
  it('stops after the first slide in a streamed body', async () => {
    const late = '<section class="slide"><h1>Should not be needed</h1></section>';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(TWO_SLIDE_DECK));
        controller.enqueue(new TextEncoder().encode(late));
        controller.close();
      },
    });
    const cover = await readDeckCoverHtml(new Response(stream));
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Should not be needed');
  });

  it('reads html from the slides deck JSON envelope', async () => {
    const res = new Response(JSON.stringify({ html: TWO_SLIDE_DECK, slug: 'deck-one' }), {
      headers: { 'content-type': 'application/json' },
    });
    const cover = await readDeckCoverHtml(res);
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Agenda');
  });
});
