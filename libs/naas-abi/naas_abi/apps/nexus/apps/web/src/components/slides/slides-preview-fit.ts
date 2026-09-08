import {
  SLIDES_PPTX_FROM_DOM_SCRIPT,
  SLIDES_PPTX_FROM_DOM_SCRIPT_ID,
} from './slides-pptx-from-dom';

/** Canonical slide stage used by Nexus deck seeds. */
export const SLIDES_STAGE_WIDTH = 1280;
export const SLIDES_STAGE_HEIGHT = 720;

/** Industry library paint box, contained into the 1280x720 stage (scale 2/3). */
export const SLIDES_INDUSTRY_STAGE_WIDTH = 1920;
export const SLIDES_INDUSTRY_STAGE_HEIGHT = 1080;
export const SLIDES_INDUSTRY_STAGE_SCALE =
  SLIDES_STAGE_WIDTH / SLIDES_INDUSTRY_STAGE_WIDTH;

/**
 * 16:9 page used by File → Print / Save as PDF.
 *
 * Width and height are already landscape. Do not add the `landscape` keyword:
 * Chrome treats `size: W H landscape` as a swap (7.5in x 13.333in) or drops
 * the rule and falls back to Letter, then shrink-to-fit leaves the next slide
 * on the same sheet.
 */
export const SLIDES_PRINT_PAGE_WIDTH_IN = '13.333in';
export const SLIDES_PRINT_PAGE_HEIGHT_IN = '7.5in';

/** Parent waits this long for an iframe ack that print() was invoked. */
export const SLIDES_PDF_EXPORT_ACK_MS = 8000;

/** postMessage channel for sandboxed preview iframes (no allow-same-origin). */
export const SLIDES_PREVIEW_MESSAGE_SOURCE = 'nexus-slides-preview';

export type SlidesPreviewToParentMessage =
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'ready' | 'metrics';
      height: number;
    }
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'export-pptx-result' | 'export-pdf-result';
      ok: boolean;
      error?: string;
    };

export type SlidesPreviewFromParentMessage = {
  source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
  type: 'export-pptx' | 'export-pdf';
};

/**
 * Present-style contain scale: fit one 16:9 stage into the available pane.
 * Letterboxing on the unused axis is expected.
 */
export function computeSlidesPreviewScale(
  availWidth: number,
  availHeight: number,
  stageWidth = SLIDES_STAGE_WIDTH,
  stageHeight = SLIDES_STAGE_HEIGHT,
): number {
  if (availWidth <= 0 || availHeight <= 0 || stageWidth <= 0 || stageHeight <= 0) {
    return 1;
  }
  return Math.min(availWidth / stageWidth, availHeight / stageHeight);
}

/** CSS injected into preview srcDoc so fixed 1280x720 slides fill the stage cleanly. */
export const SLIDES_PREVIEW_FIT_STYLE_ID = 'nexus-slides-preview-fit';
export const SLIDES_PREVIEW_BRIDGE_SCRIPT_ID = 'nexus-slides-preview-bridge';

const PREVIEW_BRIDGE_SCRIPT = `<script id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}">
(function () {
  var SOURCE = ${JSON.stringify(SLIDES_PREVIEW_MESSAGE_SOURCE)};
  var STAGE_HEIGHT = ${SLIDES_STAGE_HEIGHT};
  function reportMetrics() {
    try {
      var body = document.body;
      var el = document.documentElement;
      var measured = Math.max(
        (body && body.scrollHeight) || 0,
        (body && body.offsetHeight) || 0,
        (el && el.scrollHeight) || 0,
        (el && el.offsetHeight) || 0,
        STAGE_HEIGHT
      );
      var slides = Math.max(1, Math.round(measured / STAGE_HEIGHT));
      parent.postMessage(
        { source: SOURCE, type: 'metrics', height: slides * STAGE_HEIGHT },
        '*'
      );
    } catch (e) {}
  }
  function onReady() {
    parent.postMessage(
      { source: SOURCE, type: 'ready', height: STAGE_HEIGHT },
      '*'
    );
    reportMetrics();
    setTimeout(reportMetrics, 50);
    setTimeout(reportMetrics, 250);
  }
  window.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || data.source !== SOURCE) return;
    if (data.type === 'export-pdf') {
      try {
        if (typeof window.print !== 'function') {
          throw new Error('window.print missing');
        }
        // Ack before print() so the parent can clear its waiter. print() is
        // modal and blocks this frame; posting in the same turn can stall
        // delivery until the dialog closes, which falsely times out.
        parent.postMessage(
          { source: SOURCE, type: 'export-pdf-result', ok: true },
          '*'
        );
        setTimeout(function () {
          try {
            resetDeckForPrint();
            window.print();
          } catch (e) {}
        }, 0);
      } catch (err) {
        parent.postMessage(
          {
            source: SOURCE,
            type: 'export-pdf-result',
            ok: false,
            error: (err && err.message) || String(err),
          },
          '*'
        );
      }
      return;
    }
    if (data.type !== 'export-pptx') return;
    var build = window.buildPptx;
    if (typeof build !== 'function') {
      parent.postMessage(
        {
          source: SOURCE,
          type: 'export-pptx-result',
          ok: false,
          error: 'buildPptx missing',
        },
        '*'
      );
      return;
    }
    Promise.resolve(build())
      .then(function () {
        parent.postMessage(
          { source: SOURCE, type: 'export-pptx-result', ok: true },
          '*'
        );
      })
      .catch(function (err) {
        parent.postMessage(
          {
            source: SOURCE,
            type: 'export-pptx-result',
            ok: false,
            error: (err && err.message) || String(err),
          },
          '*'
        );
      });
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
  function resetDeckForPrint() {
    try {
      var deck = document.querySelector('main.deck, .deck');
      if (deck) {
        deck.style.transform = '';
        deck.style.marginLeft = '';
        deck.style.marginBottom = '';
        deck.style.width = '';
      }
      document.body.style.minHeight = '';
    } catch (e) {}
  }
  window.addEventListener('beforeprint', resetDeckForPrint);
  if (window.matchMedia) {
    try {
      window.matchMedia('print').addEventListener('change', function (ev) {
        if (ev.matches) resetDeckForPrint();
      });
    } catch (e) {}
  }
  window.addEventListener('load', reportMetrics);
  if (typeof ResizeObserver !== 'undefined') {
    try {
      new ResizeObserver(reportMetrics).observe(document.documentElement);
    } catch (e) {}
  }
})();
</script>`;

/** Print rules injected into every preview: one .slide = one 16:9 page. */
export const SLIDES_PREVIEW_PRINT_CSS = `
  @media print {
    @page { size: ${SLIDES_PRINT_PAGE_WIDTH_IN} ${SLIDES_PRINT_PAGE_HEIGHT_IN}; margin: 0; }
    * {
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    html, body {
      margin: 0 !important;
      padding: 0 !important;
      width: ${SLIDES_PRINT_PAGE_WIDTH_IN} !important;
      height: auto !important;
      background: #fff !important;
      overflow: visible !important;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    .deck-menubar,
    .slide-index,
    .deck-export-menu { display: none !important; }
    iframe { overflow: hidden !important; }
    body.deck-has-menubar .deck,
    .deck {
      display: block !important;
      padding: 0 !important;
      gap: 0 !important;
      margin: 0 !important;
      width: ${SLIDES_PRINT_PAGE_WIDTH_IN} !important;
      max-width: none !important;
      transform: none !important;
      zoom: 1 !important;
      overflow: visible !important;
    }
    .slide {
      display: block !important;
      position: relative !important;
      box-sizing: border-box !important;
      width: ${SLIDES_PRINT_PAGE_WIDTH_IN} !important;
      height: ${SLIDES_PRINT_PAGE_HEIGHT_IN} !important;
      max-width: none !important;
      max-height: none !important;
      margin: 0 !important;
      overflow: hidden !important;
      contain: strict !important;
      page-break-after: always !important;
      break-after: page !important;
      page-break-inside: avoid !important;
      break-inside: avoid !important;
      border: none !important;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    .slide.cover {
      display: flex !important;
      flex-direction: column !important;
    }
    .slide:first-child {
      page-break-before: auto !important;
      break-before: auto !important;
    }
    .slide:not(:first-child) {
      page-break-before: always !important;
      break-before: page !important;
    }
    .slide:last-child {
      page-break-after: auto !important;
      break-after: auto !important;
    }
    .industry-stage {
      width: ${SLIDES_INDUSTRY_STAGE_WIDTH}px !important;
      height: ${SLIDES_INDUSTRY_STAGE_HEIGHT}px !important;
      position: absolute !important;
      top: 0 !important;
      left: 0 !important;
      transform: none !important;
      zoom: ${SLIDES_INDUSTRY_STAGE_SCALE} !important;
      overflow: hidden !important;
    }
  }
`;

export function prepareSlidesPreviewHtml(html: string): string {
  if (!html) return html;
  let next = html;

  if (!next.includes(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`)) {
    const inject = `<style id="${SLIDES_PREVIEW_FIT_STYLE_ID}">
  .deck-menubar { display: none !important; }
  html, body {
    margin: 0 !important;
    overflow-x: hidden !important;
    background: transparent !important;
  }
  body.deck-has-menubar .deck,
  .deck {
    padding: 0 !important;
    gap: 0 !important;
    align-items: stretch !important;
    width: ${SLIDES_STAGE_WIDTH}px !important;
    max-width: ${SLIDES_STAGE_WIDTH}px !important;
  }
  .slide {
    width: ${SLIDES_STAGE_WIDTH}px !important;
    height: ${SLIDES_STAGE_HEIGHT}px !important;
    flex-shrink: 0 !important;
    border-left: none !important;
    border-right: none !important;
    overflow: hidden !important;
  }
${SLIDES_PREVIEW_PRINT_CSS}
</style>`;
    if (next.includes('</head>')) {
      next = next.replace('</head>', `${inject}</head>`);
    } else {
      next = `${inject}${next}`;
    }
  }

  // Override window.buildPptx so File → Export reads the live .slide DOM,
  // even when the seeded deck still has a hardcoded 4-slide exporter.
  if (!next.includes(`id="${SLIDES_PPTX_FROM_DOM_SCRIPT_ID}"`)) {
    if (next.includes('</body>')) {
      next = next.replace('</body>', `${SLIDES_PPTX_FROM_DOM_SCRIPT}</body>`);
    } else {
      next = `${next}${SLIDES_PPTX_FROM_DOM_SCRIPT}`;
    }
  }

  if (!next.includes(`id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}"`)) {
    if (next.includes('</body>')) {
      next = next.replace('</body>', `${PREVIEW_BRIDGE_SCRIPT}</body>`);
    } else {
      next = `${next}${PREVIEW_BRIDGE_SCRIPT}`;
    }
  }

  return next;
}

export function isSlidesPreviewMessage(
  data: unknown,
): data is SlidesPreviewToParentMessage {
  if (!data || typeof data !== 'object') return false;
  const msg = data as Partial<SlidesPreviewToParentMessage>;
  return msg.source === SLIDES_PREVIEW_MESSAGE_SOURCE && typeof msg.type === 'string';
}

const SECTION_RE = /<section\b([^>]*)>([\s\S]*?)<\/section>/gi;
const SLIDE_CLASS_RE = /\bclass\s*=\s*["'][^"']*\bslide\b/i;
const HEAD_RE = /<head\b[^>]*>([\s\S]*?)<\/head>/i;
const HERO_RE = /hero:\s*"((?:\\.|[^"\\])*)"/;
const HERO_MAX_CHARS = 80_000;

/** First `<section class="slide">` in a deck, or null when none is complete. */
export function extractFirstSlideHtml(html: string): string | null {
  if (!html) return null;
  SECTION_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = SECTION_RE.exec(html))) {
    if (SLIDE_CLASS_RE.test(match[1] || '')) {
      return match[0];
    }
  }
  return null;
}

export function extractHeadInnerHtml(html: string): string {
  if (!html) return '';
  const match = HEAD_RE.exec(html);
  return match ? match[1] : '';
}

/** True once head (if present) and the first slide section are complete. */
export function deckBufferHasCover(html: string): boolean {
  if (!extractFirstSlideHtml(html)) return false;
  if (/<head\b/i.test(html) && !/<\/head>/i.test(html)) return false;
  return true;
}

function stripHeadScripts(head: string): string {
  return head.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, (tag) =>
    /iconify/i.test(tag) ? tag : '',
  );
}

/** Optional `--hero` from a seed `const IMG` block, when it is a small data URL. */
export function coverHeroCss(html: string): string {
  const match = HERO_RE.exec(html);
  if (!match || match[1].length > HERO_MAX_CHARS) return '';
  const url = match[1].replace(/\\"/g, '"');
  if (!url.startsWith('data:') && !url.startsWith('http') && !url.startsWith('/')) {
    return '';
  }
  return `:root { --hero: url("${url}"); }`;
}

export const SLIDES_COVER_FIT_STYLE_ID = 'nexus-slides-cover-fit';

/**
 * First-slide srcDoc for an index card: head styles plus one `.slide`,
 * locked to the 1280x720 stage. No print/PPTX bridge.
 */
export function prepareSlidesCoverHtml(html: string): string | null {
  const slide = extractFirstSlideHtml(html);
  if (!slide) return null;
  const head = stripHeadScripts(extractHeadInnerHtml(html));
  const hero = coverHeroCss(html);
  const fit = `<style id="${SLIDES_COVER_FIT_STYLE_ID}">
  ${hero}
  .deck-menubar, .slide-index, .deck-export-menu { display: none !important; }
  html, body {
    margin: 0 !important;
    overflow: hidden !important;
    background: transparent !important;
  }
  body.deck-has-menubar .deck,
  .deck {
    padding: 0 !important;
    gap: 0 !important;
    align-items: stretch !important;
    width: ${SLIDES_STAGE_WIDTH}px !important;
    max-width: ${SLIDES_STAGE_WIDTH}px !important;
  }
  .slide {
    width: ${SLIDES_STAGE_WIDTH}px !important;
    height: ${SLIDES_STAGE_HEIGHT}px !important;
    flex-shrink: 0 !important;
    overflow: hidden !important;
  }
  .industry-stage {
    width: ${SLIDES_INDUSTRY_STAGE_WIDTH}px !important;
    height: ${SLIDES_INDUSTRY_STAGE_HEIGHT}px !important;
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    transform: scale(${SLIDES_INDUSTRY_STAGE_SCALE}) !important;
    transform-origin: top left !important;
    overflow: hidden !important;
  }
</style>`;
  return `<!doctype html><html><head>${head}${fit}</head><body><main class="deck">${slide}</main></body></html>`;
}

/**
 * Read a deck API response (`{ html }`) or a raw HTML body and keep the cover.
 * Industry decks still transfer the full JSON payload today; we strip later
 * slides before the card iframe so srcDoc is the first slide only.
 */
export async function readDeckCoverHtml(res: Response): Promise<string | null> {
  const contentType = (res.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    const body = (await res.json().catch(() => null)) as { html?: unknown } | null;
    return typeof body?.html === 'string' ? prepareSlidesCoverHtml(body.html) : null;
  }
  if (!res.body || typeof res.body.getReader !== 'function') {
    return prepareSlidesCoverHtml(await res.text());
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (value) buf += decoder.decode(value, { stream: true });
      if (done) {
        buf += decoder.decode();
        break;
      }
      if (deckBufferHasCover(buf)) {
        await reader.cancel();
        break;
      }
    }
  } catch {
    buf += decoder.decode();
  }
  return prepareSlidesCoverHtml(buf);
}
