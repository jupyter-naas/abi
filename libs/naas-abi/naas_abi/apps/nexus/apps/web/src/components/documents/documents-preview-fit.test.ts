import { describe, expect, it } from 'vitest';
import {
  computeSectionsPreviewScale,
  sectionsPreviewIndexFromScroll,
  sectionsPreviewScrollTop,
  applyDocumentsTextEdits,
  collectDocumentsTextEdits,
  countSectionSections,
  coverHeroCss,
  documentBufferHasCover,
  extractFirstSectionHtml,
  extractSectionHtmlAt,
  isSectionsPreviewMessage,
  planLetterPages,
  prepareSectionsCoverHtml,
  prepareSectionsPreviewHtml,
  readDocumentCoverHtml,
  sanitizeDocumentsEditHtml,
  SLIDES_COVER_FIT_STYLE_ID,
  SLIDES_PDF_EXPORT_ACK_MS,
  SLIDES_PREVIEW_BRIDGE_SCRIPT_ID,
  SLIDES_PREVIEW_FIT_STYLE_ID,
  SLIDES_PREVIEW_MESSAGE_SOURCE,
  SLIDES_PREVIEW_PRINT_CSS,
  SLIDES_PRINT_PAGE_HEIGHT_IN,
  SLIDES_PRINT_PAGE_WIDTH_IN,
  DOCUMENTS_PAGE_WIDTH,
  DOCUMENTS_PREVIEW_GUTTER_PX,
  SLIDES_STAGE_HEIGHT,
} from './documents-preview-fit';
import { SLIDES_PDF_FROM_DOM_SCRIPT_ID } from './documents-pptx-from-dom';

describe('planLetterPages', () => {
  it('soft-paginates by height and hard-breaks on page-break blocks', () => {
    expect(planLetterPages([{ height: 200, hardBreak: false }], 400)).toEqual([[0]]);
    expect(
      planLetterPages(
        [
          { height: 300, hardBreak: false },
          { height: 0, hardBreak: true },
          { height: 120, hardBreak: false },
        ],
        400,
      ),
    ).toEqual([[0], [2]]);
    expect(
      planLetterPages(
        [
          { height: 300, hardBreak: false },
          { height: 200, hardBreak: false },
        ],
        400,
      ),
    ).toEqual([[0], [1]]);
  });
});

describe('computeSectionsPreviewScale', () => {
  it('scales the letter column to pane width, ignoring height', () => {
    const scale = computeSectionsPreviewScale(864, 400);
    expect(scale).toBeCloseTo((864 - DOCUMENTS_PREVIEW_GUTTER_PX) / DOCUMENTS_PAGE_WIDTH, 5);
  });

  it('does not use 16:9 contain-fit', () => {
    const scale = computeSectionsPreviewScale(1600, 600);
    expect(scale).not.toBeCloseTo(600 / SLIDES_STAGE_HEIGHT, 5);
    expect(scale).toBeCloseTo((1600 - DOCUMENTS_PREVIEW_GUTTER_PX) / DOCUMENTS_PAGE_WIDTH, 5);
  });

  it('returns 1 for non-positive width', () => {
    expect(computeSectionsPreviewScale(0, 720)).toBe(1);
  });
});

describe('sectionsPreviewScrollTop', () => {
  it('maps a selected heading to host scroll from measured tops', () => {
    expect(sectionsPreviewScrollTop(0, 0.5, 0)).toBe(0);
    expect(sectionsPreviewScrollTop(2, 0.5, 400)).toBe(200);
    expect(sectionsPreviewIndexFromScroll(200, 0.5, [0, 120, 400])).toBe(2);
  });
});

describe('prepareSectionsPreviewHtml', () => {
  it('injects fit CSS and postMessage bridge once', () => {
    const src = '<!doctype html><html><head><title>t</title></head><body><main class="document"></main></body></html>';
    const once = prepareSectionsPreviewHtml(src);
    expect(once).toContain(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`);
    expect(once).toContain(`id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}"`);
    expect(once).toContain(`id="${SLIDES_PDF_FROM_DOM_SCRIPT_ID}"`);
    expect(once).toContain('window.buildPptx = buildPptx');
    expect(once).toContain(SLIDES_PREVIEW_MESSAGE_SOURCE);
    expect(once).toContain(`${DOCUMENTS_PAGE_WIDTH}px`);
    const fitStart = once.indexOf(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`);
    const screenPrintAt = once.indexOf('@media print', fitStart);
    const screenCss = once.slice(fitStart, screenPrintAt);
    expect(screenCss).toContain('transform: none !important');
    expect(screenCss).toContain('.page, .section');
    expect(screenCss).toContain('height: auto !important');
    expect(screenCss).toContain('min-height: 0 !important');
    expect(screenCss).not.toContain(`height: ${SLIDES_STAGE_HEIGHT}px`);
    expect(screenCss).toContain('nexus-documents-manual-edit');
    expect(once).toContain('set-manual-edit');
    expect(once).toContain('edit-commit');
    expect(once).toContain('contenteditable');
    expect(once).toContain('document-menubar');
    expect(once).toContain('export-pdf');
    expect(once).toContain('window.print');
    expect(once).toContain('@media print');
    expect(once).toContain('size: letter; margin: 0;');
    expect(once).not.toMatch(/@page \{[^}]*landscape/);
    expect(once).toContain('display: block !important');
    expect(once).toContain('.section-index');
    expect(once).toContain('print-color-adjust: exact');
    expect(once).toContain('letter-page');
    expect(once).toContain('isDocHeader');
    expect(once).toContain('collectRuns');
    expect(once).toContain('data-nexus-chrome-clone');
    expect(once).toContain('.letter-page > .doc-header');
    expect(once).toContain('.letter-page > .doc-footer');
    expect(once).toContain('.letter-page > .doc-footer ~ .doc-header');
    expect(once).toContain('position: relative !important');
    expect(once).toContain('page-break-after: always');
    expect(once).toContain('break-before: page');
    expect(once).not.toContain('contain: strict');
    expect(once).toContain('beforeprint');
    const ackAt = once.indexOf("type: 'export-pdf-result', ok: true");
    const printAt = once.lastIndexOf('window.print()');
    const timeoutAt = once.indexOf('setTimeout(function ()', ackAt);
    expect(ackAt).toBeGreaterThan(-1);
    expect(printAt).toBeGreaterThan(ackAt);
    expect(timeoutAt).toBeGreaterThan(ackAt);
    expect(timeoutAt).toBeLessThan(printAt);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('@media print');
    expect(SLIDES_PDF_EXPORT_ACK_MS).toBeGreaterThan(0);
    const twice = prepareSectionsPreviewHtml(once);
    expect(twice).toBe(once);
  });

  it('strips the seed viewport-fit scaler and inlines a small hero', () => {
    const src =
      '<!doctype html><html><head></head><body><main class="document"></main>' +
      '<script>const IMG = { hero: "data:image/svg+xml,hero" };</script>' +
      '<script>/* nexus-documents-viewport-fit */\n(function(){ document.style.transform = "scale(0.3)"; })();\n</script>' +
      '</body></html>';
    const out = prepareSectionsPreviewHtml(src);
    expect(out).not.toMatch(/<script>\s*\/\*\s*nexus-documents-viewport-fit/);
    expect(out).toContain(':root { --hero: url("data:image/svg+xml,hero"); }');
  });

  it('waits for every <img> before posting images-ready', () => {
    const src = '<!doctype html><html><head></head><body><main class="document"></main></body></html>';
    const out = prepareSectionsPreviewHtml(src);
    expect(out).toContain('waitForImages');
    expect(out).toContain("type: 'images-ready'");
    const onReadyAt = out.indexOf('function onReady()');
    const waitForImagesCallAt = out.indexOf('waitForImages().then');
    expect(waitForImagesCallAt).toBeGreaterThan(onReadyAt);
  });

  it('overrides a hardcoded seed buildPptx with the DOM walker', () => {
    const src =
      '<!doctype html><html><head></head><body><main class="document"></main>' +
      '<script>async function buildPptx(){ /* [["1","Context"],["2","Approach"]] */ }</script>' +
      '</body></html>';
    const out = prepareSectionsPreviewHtml(src);
    const walkerAt = out.lastIndexOf('window.buildPptx = buildPptx');
    const seedAt = out.indexOf('[["1","Context"],["2","Approach"]]');
    expect(walkerAt).toBeGreaterThan(seedAt);
    expect(out).toContain(SLIDES_PDF_FROM_DOM_SCRIPT_ID);
  });

  it('prefixes when head is missing', () => {
    const src = '<main class="document"><section class="section"></section></main>';
    const out = prepareSectionsPreviewHtml(src);
    expect(out.startsWith(`<style id="${SLIDES_PREVIEW_FIT_STYLE_ID}">`)).toBe(true);
    expect(out).toContain(`id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}"`);
  });
});

const TWO_SLIDE_DECK = `<!doctype html><html><head>
<title>Document</title>
<style>.section { background: #fff; }</style>
<script src="https://cdn.jsdelivr.net/npm/pdfgenjs@3.12.0/dist/pdfgen.bundle.js"></script>
</head><body>
<main class="document">
<section id="section-cover" class="section cover"><h1>Cover Title</h1></section>
<section class="section"><h1>Agenda</h1></section>
</main>
<script>const IMG = { hero: "data:image/svg+xml,hero" };</script>
</body></html>`;

describe('SLIDES_PREVIEW_PRINT_CSS', () => {
  it('prints each letter sheet and honors hard page breaks', () => {
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('@page { size: letter; margin: 0; }');
    expect(SLIDES_PREVIEW_PRINT_CSS).not.toMatch(/@page \{[^}]*landscape/);
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('page-break-after: always');
    expect(SLIDES_PREVIEW_PRINT_CSS).toContain('break-before: page');
    expect(SLIDES_PRINT_PAGE_WIDTH_IN).toBe('8.5in');
    expect(SLIDES_PRINT_PAGE_HEIGHT_IN).toBe('11in');
  });
});

describe('prepareSectionsCoverHtml', () => {
  it('keeps the first section and drops the rest', () => {
    const cover = prepareSectionsCoverHtml(TWO_SLIDE_DECK);
    expect(cover).toContain('Cover Title');
    expect(cover).toContain('id="section-cover"');
    expect(cover).not.toContain('Agenda');
    expect(cover).toContain(`id="${SLIDES_COVER_FIT_STYLE_ID}"`);
    expect(cover).toContain(`${DOCUMENTS_PAGE_WIDTH}px`);
    expect(cover).toContain('.page, .section');
    expect(cover).not.toContain('pdfgen');
    expect(cover).not.toContain('export-pdf');
  });

  it('returns null when no section section exists', () => {
    expect(prepareSectionsCoverHtml('<html><body>no sections</body></html>')).toBeNull();
  });

  it('builds a outline thumb for a later section', () => {
    const thumb = prepareSectionsCoverHtml(TWO_SLIDE_DECK, 1);
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

describe('documentBufferHasCover', () => {
  it('waits for a complete first section', () => {
    expect(documentBufferHasCover('<head></head><section class="section"><h1>x')).toBe(false);
    expect(documentBufferHasCover(TWO_SLIDE_DECK)).toBe(true);
  });
});

describe('extractFirstSectionHtml', () => {
  it('skips a section that is not a page or section', () => {
    const html =
      '<section class="notes">skip</section><section class="section cover"><h1>Keep</h1></section>';
    expect(extractFirstSectionHtml(html)).toContain('Keep');
    expect(extractFirstSectionHtml(html)).not.toContain('skip');
  });

  it('reads article-light page blocks', () => {
    const html =
      '<section class="page cover"><h1>Document Title</h1></section><section class="page"><h2>Introduction</h2></section>';
    expect(extractFirstSectionHtml(html)).toContain('Document Title');
    expect(countSectionSections(html)).toBe(2);
  });
});

describe('countSectionSections', () => {
  it('counts page and section blocks only', () => {
    expect(countSectionSections(TWO_SLIDE_DECK)).toBe(2);
    expect(countSectionSections('<section class="notes">x</section>')).toBe(0);
  });
});

describe('sanitizeDocumentsEditHtml', () => {
  it('drops script tags, event handlers, and javascript urls', () => {
    const dirty =
      'Hello <script>alert(1)</script><img src=x onerror="alert(1)"><a href="javascript:alert(1)">x</a>';
    const clean = sanitizeDocumentsEditHtml(dirty);
    expect(clean).toContain('Hello');
    expect(clean).not.toContain('script');
    expect(clean).not.toContain('onerror');
    expect(clean).not.toContain('javascript:');
    expect(clean).not.toContain('<img');
  });

  it('keeps bold and safe links', () => {
    expect(sanitizeDocumentsEditHtml('A <strong>B</strong>')).toBe('A <strong>B</strong>');
    expect(sanitizeDocumentsEditHtml('<a href="https://example.com">x</a>')).toContain(
      'href="https://example.com"',
    );
  });
});

describe('isSectionsPreviewMessage', () => {
  it('accepts a well-formed edit-commit and rejects a loose payload', () => {
    expect(
      isSectionsPreviewMessage({
        source: SLIDES_PREVIEW_MESSAGE_SOURCE,
        type: 'edit-commit',
        edits: [{ path: '0:h1:0', html: 'Hi' }],
      }),
    ).toBe(true);
    expect(
      isSectionsPreviewMessage({
        source: SLIDES_PREVIEW_MESSAGE_SOURCE,
        type: 'edit-commit',
      }),
    ).toBe(false);
    expect(
      isSectionsPreviewMessage({
        source: SLIDES_PREVIEW_MESSAGE_SOURCE,
        type: 'ready',
        height: 720,
      }),
    ).toBe(true);
  });
});

describe('applyDocumentsTextEdits', () => {
  it('writes one heading and leaves the other section alone', () => {
    const next = applyDocumentsTextEdits(TWO_SLIDE_DECK, [
      { path: '0:h1:0', html: 'New Cover <script>steal()</script>' },
    ]);
    expect(next).toContain('New Cover');
    expect(next).not.toContain('steal()');
    expect(next).not.toContain('Cover Title');
    expect(next).toContain('Agenda');
    expect(collectDocumentsTextEdits(TWO_SLIDE_DECK).map((e) => e.path)).toEqual([
      '0:h1:0',
      '1:h1:0',
    ]);
  });

  it('ignores unknown paths', () => {
    expect(applyDocumentsTextEdits(TWO_SLIDE_DECK, [{ path: '9:h1:0', html: 'Nope' }])).toBe(
      TWO_SLIDE_DECK,
    );
  });
});

describe('extractSectionHtmlAt', () => {
  it('returns the section at the outline index', () => {
    expect(extractSectionHtmlAt(TWO_SLIDE_DECK, 0)).toContain('Cover Title');
    expect(extractSectionHtmlAt(TWO_SLIDE_DECK, 1)).toContain('Agenda');
    expect(extractSectionHtmlAt(TWO_SLIDE_DECK, 1)).not.toContain('Cover Title');
    expect(extractSectionHtmlAt(TWO_SLIDE_DECK, 2)).toBeNull();
    expect(extractSectionHtmlAt('', 0)).toBeNull();
  });
});

describe('readDocumentCoverHtml', () => {
  it('stops after the first section in a streamed body', async () => {
    const late = '<section class="section"><h1>Should not be needed</h1></section>';
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(TWO_SLIDE_DECK));
        controller.enqueue(new TextEncoder().encode(late));
        controller.close();
      },
    });
    const cover = await readDocumentCoverHtml(new Response(stream));
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Should not be needed');
  });

  it('reads html from the sections document JSON envelope', async () => {
    const res = new Response(JSON.stringify({ html: TWO_SLIDE_DECK, slug: 'document-one' }), {
      headers: { 'content-type': 'application/json' },
    });
    const cover = await readDocumentCoverHtml(res);
    expect(cover).toContain('Cover Title');
    expect(cover).not.toContain('Agenda');
  });
});
