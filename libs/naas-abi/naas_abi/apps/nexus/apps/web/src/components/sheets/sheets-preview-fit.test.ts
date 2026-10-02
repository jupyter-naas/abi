import { describe, expect, it } from 'vitest';
import {
  computeSheetsPreviewScale,
  sheetsPreviewIndexFromScroll,
  sheetsPreviewScrollTop,
  applySheetsTextEdits,
  collectSheetsTextEdits,
  countSlideSections,
  coverHeroCss,
  workbookBufferHasCover,
  extractFirstSlideHtml,
  extractSlideHtmlAt,
  isSheetsPreviewMessage,
  prepareSheetsCoverHtml,
  prepareSheetsPreviewHtml,
  readWorkbookCoverHtml,
  sanitizeSheetsEditHtml,
  SHEETS_COVER_FIT_STYLE_ID,
  SHEETS_INDUSTRY_STAGE_SCALE,
  SHEETS_PREVIEW_BRIDGE_SCRIPT_ID,
  SHEETS_PREVIEW_FIT_STYLE_ID,
  SHEETS_PREVIEW_MESSAGE_SOURCE,
  SHEETS_PREVIEW_PRINT_CSS,
  SHEETS_PRINT_PAGE_HEIGHT_IN,
  SHEETS_PRINT_PAGE_WIDTH_IN,
  SHEETS_STAGE_HEIGHT,
  SHEETS_STAGE_WIDTH,
} from './sheets-preview-fit';

describe('computeSheetsPreviewScale', () => {
  it('contains a 16:9 stage in a wide pane (letterbox top/bottom)', () => {
    const scale = computeSheetsPreviewScale(1600, 600);
    expect(scale).toBeCloseTo(600 / SHEETS_STAGE_HEIGHT, 5);
  });

  it('contains a 16:9 stage in a tall pane (pillarbox left/right)', () => {
    const scale = computeSheetsPreviewScale(800, 900);
    expect(scale).toBeCloseTo(800 / SHEETS_STAGE_WIDTH, 5);
  });

  it('returns 1 for non-positive inputs', () => {
    expect(computeSheetsPreviewScale(0, 720)).toBe(1);
    expect(computeSheetsPreviewScale(1280, -1)).toBe(1);
  });
});

describe('sheetsPreviewScrollTop', () => {
  it('maps a selected index to host scroll at the current scale', () => {
    expect(sheetsPreviewScrollTop(0, 0.5)).toBe(0);
    expect(sheetsPreviewScrollTop(2, 0.5)).toBe(2 * SHEETS_STAGE_HEIGHT * 0.5);
    expect(sheetsPreviewIndexFromScroll(SHEETS_STAGE_HEIGHT * 0.5, 0.5)).toBe(1);
  });
});

describe('prepareSheetsPreviewHtml', () => {
  it('injects fit CSS and postMessage bridge once', () => {
    const src = '<!doctype html><html><head><title>t</title></head><body><main class="workbook"></main></body></html>';
    const once = prepareSheetsPreviewHtml(src);
    expect(once).toContain(`id="${SHEETS_PREVIEW_FIT_STYLE_ID}"`);
    expect(once).toContain(`id="${SHEETS_PREVIEW_BRIDGE_SCRIPT_ID}"`);
    expect(once).not.toContain('window.buildPptx');
    expect(once).not.toContain('export-pptx');
    expect(once).toContain(SHEETS_PREVIEW_MESSAGE_SOURCE);
    expect(once).toContain(`${SHEETS_STAGE_WIDTH}px`);
    const fitStart = once.indexOf(`id="${SHEETS_PREVIEW_FIT_STYLE_ID}"`);
    const screenPrintAt = once.indexOf('@media print', fitStart);
    const screenCss = once.slice(fitStart, screenPrintAt);
    expect(screenCss).toContain('transform: none !important');
    expect(screenCss).toContain('margin-left: 0 !important');
    expect(screenCss).toContain('margin-bottom: 0 !important');
    expect(screenCss).toContain('.industry-stage');
    expect(screenCss).toContain(`transform: scale(${SHEETS_INDUSTRY_STAGE_SCALE})`);
    expect(screenCss).toContain('nexus-sheets-manual-edit');
    expect(once).toContain('set-manual-edit');
    expect(once).toContain('edit-commit');
    expect(once).toContain('contenteditable');
    expect(once).toContain('workbook-menubar');
    expect(once).not.toContain('export-pdf');
    expect(once).toContain('@media print');
    expect(once).toContain(`size: ${SHEETS_PRINT_PAGE_WIDTH_IN} ${SHEETS_PRINT_PAGE_HEIGHT_IN}; margin: 0;`);
    expect(once).not.toMatch(/@page \{[^}]*landscape/);
    expect(once).toContain('display: block !important');
    expect(once).toContain('.slide-index');
    expect(once).toContain('.industry-stage');
    expect(once).toContain(`zoom: ${SHEETS_INDUSTRY_STAGE_SCALE}`);
    expect(once).toContain('print-color-adjust: exact');
    expect(once).toContain('page-break-after: always');
    expect(once).toContain('page-break-before: always');
    expect(once).toContain('contain: strict');
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain('@media print');
    const twice = prepareSheetsPreviewHtml(once);
    expect(twice).toBe(once);
  });

  it('strips the seed viewport-fit scaler and inlines a small hero', () => {
    const src =
      '<!doctype html><html><head></head><body><main class="workbook"></main>' +
      '<script>const IMG = { hero: "data:image/svg+xml,hero" };</script>' +
      '<script>/* nexus-sheets-viewport-fit */\n(function(){ workbook.style.transform = "scale(0.3)"; })();\n</script>' +
      '</body></html>';
    const out = prepareSheetsPreviewHtml(src);
    expect(out).not.toMatch(/<script>\s*\/\*\s*nexus-sheets-viewport-fit/);
    expect(out).toContain(':root { --hero: url("data:image/svg+xml,hero"); }');
  });

  it('waits for every <img> before posting images-ready', () => {
    const src = '<!doctype html><html><head></head><body><main class="workbook"></main></body></html>';
    const out = prepareSheetsPreviewHtml(src);
    expect(out).toContain('waitForImages');
    expect(out).toContain("type: 'images-ready'");
    const onReadyAt = out.indexOf('function onReady()');
    const waitForImagesCallAt = out.indexOf('waitForImages().then');
    expect(waitForImagesCallAt).toBeGreaterThan(onReadyAt);
  });

  it('prefixes when head is missing', () => {
    const src = '<main class="workbook"><section class="slide"></section></main>';
    const out = prepareSheetsPreviewHtml(src);
    expect(out.startsWith(`<style id="${SHEETS_PREVIEW_FIT_STYLE_ID}">`)).toBe(true);
    expect(out).toContain(`id="${SHEETS_PREVIEW_BRIDGE_SCRIPT_ID}"`);
  });
});

const TWO_SLIDE_DECK = `<!doctype html><html><head>
<title>Workbook</title>
<style>.slide { background: #fff; }</style>
<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js"></script>
</head><body>
<main class="workbook">
<section id="slide-cover" class="slide cover"><h1>Cover Title</h1></section>
<section class="slide"><h1>Agenda</h1></section>
</main>
<script>const IMG = { hero: "data:image/svg+xml,hero" };</script>
</body></html>`;

describe('SHEETS_PREVIEW_PRINT_CSS', () => {
  it('sizes the page and each slide in the same inches, without landscape', () => {
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain(
      `@page { size: ${SHEETS_PRINT_PAGE_WIDTH_IN} ${SHEETS_PRINT_PAGE_HEIGHT_IN}; margin: 0; }`,
    );
    expect(SHEETS_PREVIEW_PRINT_CSS).not.toMatch(/@page \{[^}]*landscape/);
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain(`width: ${SHEETS_PRINT_PAGE_WIDTH_IN} !important`);
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain(`height: ${SHEETS_PRINT_PAGE_HEIGHT_IN} !important`);
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain('max-width: none !important');
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain('max-height: none !important');
  });

  it('uses zoom for the industry paint box so print layout is 1280x720', () => {
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain(`zoom: ${SHEETS_INDUSTRY_STAGE_SCALE} !important`);
    expect(SHEETS_PREVIEW_PRINT_CSS).toContain('transform: none !important');
    expect(SHEETS_PREVIEW_PRINT_CSS).not.toContain(
      `transform: scale(${SHEETS_INDUSTRY_STAGE_SCALE})`,
    );
  });
});

describe('prepareSheetsCoverHtml', () => {
  it('keeps the first slide and drops the rest', () => {
    const cover = prepareSheetsCoverHtml(TWO_SLIDE_DECK);
    expect(cover).toContain('Cover Title');
    expect(cover).toContain('id="slide-cover"');
    expect(cover).not.toContain('Agenda');
    expect(cover).toContain(`id="${SHEETS_COVER_FIT_STYLE_ID}"`);
    expect(cover).toContain('.industry-stage');
    expect(cover).toContain(`transform: scale(${SHEETS_INDUSTRY_STAGE_SCALE})`);
    expect(cover).not.toContain('pptxgen');
    expect(cover).not.toContain('export-pdf');
  });

  it('returns null when no slide section exists', () => {
    expect(prepareSheetsCoverHtml('<html><body>no sheets</body></html>')).toBeNull();
  });

  it('builds a filmstrip thumb for a later slide', () => {
    const thumb = prepareSheetsCoverHtml(TWO_SLIDE_DECK, 1);
    expect(thumb).toContain('Agenda');
    expect(thumb).not.toContain('Cover Title');
    expect(thumb).toContain(`id="${SHEETS_COVER_FIT_STYLE_ID}"`);
  });

  it('reads a small hero data URL for the cover band', () => {
    expect(coverHeroCss(TWO_SLIDE_DECK)).toContain('data:image/svg+xml,hero');
  });

  it('allows a relative assets/ hero after seed extraction', () => {
    const html = 'const IMG = { hero: "assets/img-001.jpg" };';
    expect(coverHeroCss(html)).toContain('url("assets/img-001.jpg")');
  });
});

describe('workbookBufferHasCover', () => {
  it('waits for a complete first slide', () => {
    expect(workbookBufferHasCover('<head></head><section class="slide"><h1>x')).toBe(false);
    expect(workbookBufferHasCover(TWO_SLIDE_DECK)).toBe(true);
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

describe('countSlideSections', () => {
  it('counts slide sections only', () => {
    expect(countSlideSections(TWO_SLIDE_DECK)).toBe(2);
    expect(countSlideSections('<section class="notes">x</section>')).toBe(0);
  });
});

describe('sanitizeSheetsEditHtml', () => {
  it('drops script tags, event handlers, and javascript urls', () => {
    const dirty =
      'Hello <script>alert(1)</script><img src=x onerror="alert(1)"><a href="javascript:alert(1)">x</a>';
    const clean = sanitizeSheetsEditHtml(dirty);
    expect(clean).toContain('Hello');
    expect(clean).not.toContain('script');
    expect(clean).not.toContain('onerror');
    expect(clean).not.toContain('javascript:');
    expect(clean).not.toContain('<img');
  });

  it('keeps bold and safe links', () => {
    expect(sanitizeSheetsEditHtml('A <strong>B</strong>')).toBe('A <strong>B</strong>');
    expect(sanitizeSheetsEditHtml('<a href="https://example.com">x</a>')).toContain(
      'href="https://example.com"',
    );
  });
});

describe('isSheetsPreviewMessage', () => {
  it('accepts a well-formed edit-commit and rejects a loose payload', () => {
    expect(
      isSheetsPreviewMessage({
        source: SHEETS_PREVIEW_MESSAGE_SOURCE,
        type: 'edit-commit',
        edits: [{ path: '0:h1:0', html: 'Hi' }],
      }),
    ).toBe(true);
    expect(
      isSheetsPreviewMessage({
        source: SHEETS_PREVIEW_MESSAGE_SOURCE,
        type: 'edit-commit',
      }),
    ).toBe(false);
    expect(
      isSheetsPreviewMessage({
        source: SHEETS_PREVIEW_MESSAGE_SOURCE,
        type: 'ready',
        height: 720,
      }),
    ).toBe(true);
  });
});

describe('applySheetsTextEdits', () => {
  it('writes one heading and leaves the other slide alone', () => {
    const next = applySheetsTextEdits(TWO_SLIDE_DECK, [
      { path: '0:h1:0', html: 'New Cover <script>steal()</script>' },
    ]);
    expect(next).toContain('New Cover');
    expect(next).not.toContain('steal()');
    expect(next).not.toContain('Cover Title');
    expect(next).toContain('Agenda');
    expect(collectSheetsTextEdits(TWO_SLIDE_DECK).map((e) => e.path)).toEqual([
      '0:h1:0',
      '1:h1:0',
    ]);
  });

  it('ignores unknown paths', () => {
    expect(applySheetsTextEdits(TWO_SLIDE_DECK, [{ path: '9:h1:0', html: 'Nope' }])).toBe(
      TWO_SLIDE_DECK,
    );
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

describe('readWorkbookCoverHtml', () => {
  it('stops after the first slide in a streamed body', async () => {
    const late = '<section class="slide"><h1>Should not be needed</h1></section>';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(TWO_SLIDE_DECK));
        controller.enqueue(new TextEncoder().encode(late));
        controller.close();
      },
    });
    const cover = await readWorkbookCoverHtml(new Response(stream));
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Should not be needed');
  });

  it('reads html from the sheets workbook JSON envelope', async () => {
    const res = new Response(JSON.stringify({ html: TWO_SLIDE_DECK, slug: 'workbook-one' }), {
      headers: { 'content-type': 'application/json' },
    });
    const cover = await readWorkbookCoverHtml(res);
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Agenda');
  });
});
