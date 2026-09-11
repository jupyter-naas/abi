import {
  SLIDES_PDF_FROM_DOM_SCRIPT,
  SLIDES_PDF_FROM_DOM_SCRIPT_ID,
} from './documents-pptx-from-dom';

/** Letter content width (8.5in at 96dpi). Reading column, not a 16:9 stage. */
export const DOCUMENTS_PAGE_WIDTH = 816;
/** Letter page height at 96dpi. Minimum paper, not a per-section canvas. */
export const DOCUMENTS_PAGE_MIN_HEIGHT = 1056;
export const DOCUMENTS_PREVIEW_GUTTER_PX = 48;

/**
 * Legacy names from the Slides fork. Preview and thumbs use DOCUMENTS_PAGE_*.
 * PDF planner still reads these for the leftover 16:9 reconstruction path.
 */
export const SLIDES_STAGE_WIDTH = 1280;
export const SLIDES_STAGE_HEIGHT = 720;

/** Industry library paint box (unused by article seeds). */
export const SLIDES_INDUSTRY_STAGE_WIDTH = 1920;
export const SLIDES_INDUSTRY_STAGE_HEIGHT = 1080;
export const SLIDES_INDUSTRY_STAGE_SCALE =
  DOCUMENTS_PAGE_WIDTH / SLIDES_INDUSTRY_STAGE_WIDTH;

/** Letter sheet used by File → Print / Save as PDF. */
export const SLIDES_PRINT_PAGE_WIDTH_IN = '8.5in';
export const SLIDES_PRINT_PAGE_HEIGHT_IN = '11in';

/** Parent waits this long for an iframe ack that print() was invoked. */
export const SLIDES_PDF_EXPORT_ACK_MS = 8000;

/**
 * Parent reveals the preview after this long even without an `images-ready`
 * ack (broken bridge injection, hostile document script, etc.). A stuck spinner
 * is worse than a section that finishes painting a beat late.
 */
export const SLIDES_PREVIEW_IMAGES_READY_TIMEOUT_MS = 6000;

/** postMessage channel for sandboxed preview iframes (no allow-same-origin). */
export const SLIDES_PREVIEW_MESSAGE_SOURCE = 'nexus-documents-preview';

export type SectionsPreviewToParentMessage =
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      /**
       * 'ready' fires on DOMContentLoaded (markup parsed, images may still be
       * decoding); 'images-ready' fires once every `<img>` has loaded or
       * errored, so the parent can hold the preview hidden until sections are
       * visually complete instead of flashing in with blank image boxes.
       */
      type: 'ready' | 'metrics' | 'images-ready';
      height: number;
      sectionTops?: number[];
    }
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'export-pdf-result' | 'export-pdf-result';
      ok: boolean;
      error?: string;
    }
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'edit-commit';
      edits: DocumentsTextEdit[];
    };

export type SectionsPreviewFromParentMessage =
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'export-pdf' | 'export-pdf';
    }
  | {
      source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
      type: 'set-manual-edit';
      enabled: boolean;
    };

/** Path is ``{sectionIndex}:{tag}:{nth}`` among non-nested editable tags in that section. */
export type DocumentsTextEdit = { path: string; html: string };

/** Idle commit after typing in Manual edit (blur/Escape commit immediately). */
export const DOCUMENTS_MANUAL_EDIT_IDLE_MS = 600;

export const SLIDES_EDITABLE_TAGS = [
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'p',
  'li',
  'button',
  'a',
  'figcaption',
  'blockquote',
  'label',
  'td',
  'th',
] as const;

const SLIDES_EDITABLE_TAG_SET = new Set<string>(SLIDES_EDITABLE_TAGS);

const SLIDES_EDIT_PATH_RE = /^(\d+):([a-z][a-z0-9]*):(\d+)$/;

/** Phrasing tags kept when applying a Manual edit. Scripts and handlers are dropped. */
const SLIDES_EDIT_HTML_ALLOWED = new Set([
  'br',
  'span',
  'strong',
  'em',
  'b',
  'i',
  'u',
  'small',
  'mark',
  'sub',
  'sup',
  'a',
]);

/**
 * Width-only scale: fit the letter column into the pane. Height follows the
 * prose, so the host scrolls like a Word page, not a 16:9 contain-fit.
 */
export function computeSectionsPreviewScale(
  availWidth: number,
  _availHeight?: number,
  pageWidth = DOCUMENTS_PAGE_WIDTH,
  gutter = DOCUMENTS_PREVIEW_GUTTER_PX,
): number {
  if (availWidth <= 0 || pageWidth <= 0) {
    return 1;
  }
  return Math.max(0.05, (availWidth - gutter) / pageWidth);
}

/** Host scrollTop that brings a heading block into view at the current scale. */
export function sectionsPreviewScrollTop(
  index: number,
  scale: number,
  sectionTop = 0,
): number {
  if (index <= 0 || scale <= 0) return 0;
  return sectionTop * scale;
}

export function sectionsPreviewIndexFromScroll(
  scrollTop: number,
  scale: number,
  sectionTops: number[] = [],
): number {
  if (scale <= 0 || !sectionTops.length) return 0;
  const y = scrollTop / scale;
  let best = 0;
  for (let i = 0; i < sectionTops.length; i += 1) {
    if (y + 32 >= sectionTops[i]) best = i;
  }
  return best;
}

/** CSS injected into preview srcDoc so fixed 816px prose sections fill the stage cleanly. */
export const SLIDES_PREVIEW_FIT_STYLE_ID = 'nexus-documents-preview-fit';
export const SLIDES_PREVIEW_BRIDGE_SCRIPT_ID = 'nexus-documents-preview-bridge';

const PREVIEW_BRIDGE_SCRIPT = `<script id="${SLIDES_PREVIEW_BRIDGE_SCRIPT_ID}">
(function () {
  var SOURCE = ${JSON.stringify(SLIDES_PREVIEW_MESSAGE_SOURCE)};
  var PAGE_MIN_HEIGHT = ${DOCUMENTS_PAGE_MIN_HEIGHT};
  function sectionNodes() {
    return Array.prototype.slice.call(
      document.querySelectorAll(
        'main.document > section.page, main.document > section.section, .document > section.page, .document > section.section'
      )
    );
  }
  function measureHeight() {
    var body = document.body;
    var el = document.documentElement;
    var measured = Math.max(
      (body && body.scrollHeight) || 0,
      (body && body.offsetHeight) || 0,
      (el && el.scrollHeight) || 0,
      (el && el.offsetHeight) || 0,
      PAGE_MIN_HEIGHT
    );
    return measured;
  }
  function reportMetrics() {
    try {
      parent.postMessage(
        {
          source: SOURCE,
          type: 'metrics',
          height: measureHeight(),
          sectionTops: sectionNodes().map(function (node) {
            return node.offsetTop || 0;
          }),
        },
        '*'
      );
    } catch (e) {}
  }
  function waitForImages() {
    var imgs;
    try {
      imgs = Array.prototype.slice.call(document.images || []);
    } catch (e) {
      return Promise.resolve();
    }
    if (!imgs.length) return Promise.resolve();
    return Promise.all(
      imgs.map(function (img) {
        if (img.complete) return Promise.resolve();
        return new Promise(function (resolve) {
          img.addEventListener('load', resolve, { once: true });
          img.addEventListener('error', resolve, { once: true });
        });
      })
    );
  }
  function onReady() {
    parent.postMessage(
      { source: SOURCE, type: 'ready', height: measureHeight() },
      '*'
    );
    reportMetrics();
    setTimeout(reportMetrics, 50);
    setTimeout(reportMetrics, 250);
    waitForImages().then(function () {
      parent.postMessage(
        { source: SOURCE, type: 'images-ready', height: measureHeight() },
        '*'
      );
      reportMetrics();
    });
  }
  var EDIT_SEL = 'h1,h2,h3,h4,h5,h6,p,li,button,a,figcaption,blockquote,label,td,th';
  var EDIT_ATTR = 'data-nexus-edit';
  var editEnabled = false;
  var editIdle = null;
  function sectionSections() {
    return sectionNodes();
  }
  function isNestedEditable(el, section) {
    var p = el.parentElement;
    while (p && p !== section) {
      if (p.matches && p.matches(EDIT_SEL)) return true;
      p = p.parentElement;
    }
    return false;
  }
  function tagEditTargets() {
    var list = [];
    sectionSections().forEach(function (section, si) {
      var counts = {};
      Array.prototype.slice.call(section.querySelectorAll(EDIT_SEL)).forEach(function (el) {
        if (isNestedEditable(el, section)) return;
        var tag = (el.tagName || '').toLowerCase();
        if (!counts[tag]) counts[tag] = 0;
        el.setAttribute(EDIT_ATTR, si + ':' + tag + ':' + counts[tag]);
        counts[tag] += 1;
        list.push(el);
      });
    });
    return list;
  }
  function collectEdits() {
    return tagEditTargets().map(function (el) {
      return { path: el.getAttribute(EDIT_ATTR), html: el.innerHTML || '' };
    });
  }
  function commitEdits() {
    parent.postMessage({ source: SOURCE, type: 'edit-commit', edits: collectEdits() }, '*');
  }
  function scheduleEditCommit() {
    if (editIdle) clearTimeout(editIdle);
    editIdle = setTimeout(function () {
      editIdle = null;
      commitEdits();
    }, ${DOCUMENTS_MANUAL_EDIT_IDLE_MS});
  }
  function setManualEdit(on) {
    editEnabled = !!on;
    document.documentElement.classList.toggle('nexus-documents-manual-edit', editEnabled);
    tagEditTargets().forEach(function (el) {
      if (editEnabled) {
        el.setAttribute('contenteditable', 'true');
        el.setAttribute('spellcheck', 'true');
      } else {
        el.removeAttribute('contenteditable');
      }
    });
    if (!editEnabled) {
      if (editIdle) {
        clearTimeout(editIdle);
        editIdle = null;
      }
      commitEdits();
    }
  }
  document.addEventListener('focusout', function (event) {
    if (!editEnabled) return;
    var el = event.target;
    if (!el || !el.getAttribute || !el.getAttribute(EDIT_ATTR)) return;
    commitEdits();
  });
  document.addEventListener('input', function (event) {
    if (!editEnabled) return;
    var el = event.target;
    if (!el || !el.getAttribute || !el.getAttribute(EDIT_ATTR)) return;
    scheduleEditCommit();
  });
  document.addEventListener('keydown', function (event) {
    if (!editEnabled || event.key !== 'Escape') return;
    var active = document.activeElement;
    if (active && active.blur) active.blur();
    commitEdits();
    event.preventDefault();
  });
  window.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || data.source !== SOURCE) return;
    if (data.type === 'set-manual-edit') {
      setManualEdit(!!data.enabled);
      return;
    }
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
            resetDocumentForPrint();
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
    if (data.type !== 'export-pdf') return;
    var build = window.buildPptx;
    if (typeof build !== 'function') {
      parent.postMessage(
        {
          source: SOURCE,
          type: 'export-pdf-result',
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
          { source: SOURCE, type: 'export-pdf-result', ok: true },
          '*'
        );
      })
      .catch(function (err) {
        parent.postMessage(
          {
            source: SOURCE,
            type: 'export-pdf-result',
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
  function resetDocumentForPrint() {
    try {
      var root = document.querySelector('main.document, .document');
      if (root) {
        root.style.transform = '';
        root.style.marginLeft = '';
        root.style.marginBottom = '';
        root.style.width = '';
      }
      document.body.style.minHeight = '';
    } catch (e) {}
  }
  window.addEventListener('beforeprint', resetDocumentForPrint);
  if (window.matchMedia) {
    try {
      window.matchMedia('print').addEventListener('change', function (ev) {
        if (ev.matches) resetDocumentForPrint();
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

/** Print rules: continuous letter prose. The browser paginates; sections are headings. */
export const SLIDES_PREVIEW_PRINT_CSS = `
  @media print {
    @page { size: letter; margin: 1in; }
    * {
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    html, body {
      margin: 0 !important;
      padding: 0 !important;
      width: auto !important;
      height: auto !important;
      background: #fff !important;
      overflow: visible !important;
    }
    .document-menubar,
    .section-index,
    .document-export-menu { display: none !important; }
    body.document-has-menubar .document,
    .document {
      display: block !important;
      padding: 0 !important;
      gap: 0 !important;
      margin: 0 !important;
      width: auto !important;
      max-width: none !important;
      min-height: 0 !important;
      box-shadow: none !important;
      transform: none !important;
      zoom: 1 !important;
      overflow: visible !important;
    }
    .page, .section {
      display: block !important;
      position: relative !important;
      width: auto !important;
      height: auto !important;
      min-height: 0 !important;
      max-width: none !important;
      max-height: none !important;
      margin: 0 0 1.25em !important;
      padding: 0 !important;
      overflow: visible !important;
      contain: none !important;
      page-break-after: auto !important;
      break-after: auto !important;
      page-break-inside: auto !important;
      break-inside: auto !important;
      border: none !important;
      box-shadow: none !important;
      background: transparent !important;
    }
    h1, h2, h3 {
      page-break-after: avoid !important;
      break-after: avoid !important;
    }
  }
`;

const VIEWPORT_FIT_SCRIPT_RE =
  /<script>\s*\/\*\s*nexus-documents-viewport-fit\s*\*\/[\s\S]*?<\/script>/gi;

export function prepareSectionsPreviewHtml(html: string): string {
  if (!html) return html;
  let next = html.replace(VIEWPORT_FIT_SCRIPT_RE, '');

  if (!next.includes(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`)) {
    const hero = coverHeroCss(html);
    const inject = `<style id="${SLIDES_PREVIEW_FIT_STYLE_ID}">
  ${hero}
  .document-menubar { display: none !important; }
  html, body {
    margin: 0 !important;
    overflow-x: hidden !important;
    background: #e8e6e1 !important;
    min-height: 0 !important;
  }
  body.document-has-menubar .document,
  .document {
    display: block !important;
    padding: 72px 80px 96px !important;
    gap: 0 !important;
    align-items: stretch !important;
    width: ${DOCUMENTS_PAGE_WIDTH}px !important;
    max-width: ${DOCUMENTS_PAGE_WIDTH}px !important;
    min-height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    background: #fff !important;
    box-shadow: 0 1px 3px rgba(26, 26, 26, 0.08) !important;
    transform: none !important;
    margin: 0 auto !important;
  }
  .page, .section {
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    margin: 0 0 1.5em !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    overflow: visible !important;
    flex-shrink: 1 !important;
  }
  .page:last-child, .section:last-child {
    margin-bottom: 0 !important;
  }
  html.nexus-documents-manual-edit [data-nexus-edit] {
    cursor: text;
    outline: 1px dashed rgba(37, 99, 235, 0.35);
    outline-offset: 2px;
  }
  html.nexus-documents-manual-edit [data-nexus-edit]:focus {
    outline: 2px solid rgba(37, 99, 235, 0.75);
    outline-offset: 2px;
  }
${SLIDES_PREVIEW_PRINT_CSS}
</style>`;
    if (next.includes('</head>')) {
      next = next.replace('</head>', `${inject}</head>`);
    } else {
      next = `${inject}${next}`;
    }
  }

  // Override window.buildPptx so File → Export reads the live .section DOM,
  // even when the seeded document still has a hardcoded 4-section exporter.
  if (!next.includes(`id="${SLIDES_PDF_FROM_DOM_SCRIPT_ID}"`)) {
    if (next.includes('</body>')) {
      next = next.replace('</body>', `${SLIDES_PDF_FROM_DOM_SCRIPT}</body>`);
    } else {
      next = `${next}${SLIDES_PDF_FROM_DOM_SCRIPT}`;
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

function isDocumentsTextEdit(row: unknown): row is DocumentsTextEdit {
  if (!row || typeof row !== 'object') return false;
  const edit = row as Partial<DocumentsTextEdit>;
  return typeof edit.path === 'string' && typeof edit.html === 'string';
}

export function isSectionsPreviewMessage(
  data: unknown,
): data is SectionsPreviewToParentMessage {
  if (!data || typeof data !== 'object') return false;
  const msg = data as { source?: unknown; type?: unknown; edits?: unknown };
  if (msg.source !== SLIDES_PREVIEW_MESSAGE_SOURCE || typeof msg.type !== 'string') {
    return false;
  }
  if (msg.type === 'edit-commit') {
    return Array.isArray(msg.edits) && msg.edits.every(isDocumentsTextEdit);
  }
  return true;
}

const SECTION_RE = /<section\b([^>]*)>([\s\S]*?)<\/section>/gi;
const SLIDE_CLASS_RE = /\bclass\s*=\s*["'][^"']*\b(?:page|section)\b/i;
const HEAD_RE = /<head\b[^>]*>([\s\S]*?)<\/head>/i;
const HERO_RE = /hero:\s*"((?:\\.|[^"\\])*)"/;
const HERO_MAX_CHARS = 80_000;

/** The `index`-th `<section class="page|section">`, or null when that block is missing. */
export function extractSectionHtmlAt(html: string, index: number): string | null {
  if (!html || index < 0) return null;
  SECTION_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  let seen = 0;
  while ((match = SECTION_RE.exec(html))) {
    if (SLIDE_CLASS_RE.test(match[1] || '')) {
      if (seen === index) return match[0];
      seen += 1;
    }
  }
  return null;
}

/** First `<section class="page|section">` in a document, or null when none is complete. */
export function extractFirstSectionHtml(html: string): string | null {
  return extractSectionHtmlAt(html, 0);
}

export function extractHeadInnerHtml(html: string): string {
  if (!html) return '';
  const match = HEAD_RE.exec(html);
  return match ? match[1] : '';
}

/** True once head (if present) and the first section section are complete. */
export function documentBufferHasCover(html: string): boolean {
  if (!extractFirstSectionHtml(html)) return false;
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
  if (
    !url.startsWith('data:') &&
    !url.startsWith('http') &&
    !url.startsWith('/') &&
    !url.startsWith('assets/')
  ) {
    return '';
  }
  return `:root { --hero: url("${url}"); }`;
}

export const SLIDES_COVER_FIT_STYLE_ID = 'nexus-documents-cover-fit';

/**
 * Top-of-page srcDoc for an index card: letter column, no 16:9 lock, no print bridge.
 * `index` defaults to the first heading block.
 */
export function prepareSectionsCoverHtml(html: string, index = 0): string | null {
  const section = extractSectionHtmlAt(html, index);
  if (!section) return null;
  const head = stripHeadScripts(extractHeadInnerHtml(html));
  const hero = coverHeroCss(html);
  const fit = `<style id="${SLIDES_COVER_FIT_STYLE_ID}">
  ${hero}
  .document-menubar, .section-index, .document-export-menu { display: none !important; }
  html, body {
    margin: 0 !important;
    overflow: hidden !important;
    background: #e8e6e1 !important;
  }
  body.document-has-menubar .document,
  .document {
    padding: 56px 64px 48px !important;
    gap: 0 !important;
    align-items: stretch !important;
    width: ${DOCUMENTS_PAGE_WIDTH}px !important;
    max-width: ${DOCUMENTS_PAGE_WIDTH}px !important;
    min-height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    background: #fff !important;
  }
  .page, .section {
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    overflow: visible !important;
  }
</style>`;
  return `<!doctype html><html><head>${head}${fit}</head><body><main class="document">${section}</main></body></html>`;
}

/**
 * Read a document API response (`{ html }`) or a raw HTML body and keep the cover.
 * Industry documents still transfer the full JSON payload today; we strip later
 * sections before the card iframe so srcDoc is the first section only.
 */
export async function readDocumentCoverHtml(res: Response): Promise<string | null> {
  const contentType = (res.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('application/json')) {
    const body = (await res.json().catch(() => null)) as { html?: unknown } | null;
    return typeof body?.html === 'string' ? prepareSectionsCoverHtml(body.html) : null;
  }
  if (!res.body || typeof res.body.getReader !== 'function') {
    return prepareSectionsCoverHtml(await res.text());
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
      if (documentBufferHasCover(buf)) {
        await reader.cancel();
        break;
      }
    }
  } catch {
    buf += decoder.decode();
  }
  return prepareSectionsCoverHtml(buf);
}

type SectionsEditNode = {
  tag: string;
  innerStart: number;
  innerEnd: number;
  inner: string;
};

/** Number of ``<section class="page|section">`` blocks. */
export function countSectionSections(html: string): number {
  if (!html) return 0;
  let index = 0;
  while (extractSectionHtmlAt(html, index)) {
    index += 1;
  }
  return index;
}

function listEditableNodes(fragment: string): SectionsEditNode[] {
  const re = /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g;
  const stack: Array<{ tag: string; innerStart: number }> = [];
  const nodes: SectionsEditNode[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(fragment))) {
    const raw = match[0];
    const tag = match[1].toLowerCase();
    if (!SLIDES_EDITABLE_TAG_SET.has(tag)) continue;
    if (raw.startsWith('</')) {
      for (let i = stack.length - 1; i >= 0; i -= 1) {
        if (stack[i].tag === tag) {
          const open = stack[i];
          nodes.push({
            tag,
            innerStart: open.innerStart,
            innerEnd: match.index,
            inner: fragment.slice(open.innerStart, match.index),
          });
          stack.splice(i, 1);
          break;
        }
      }
    } else if (!/\/\s*>$/.test(raw)) {
      stack.push({ tag, innerStart: match.index + raw.length });
    }
  }
  nodes.sort((a, b) => a.innerStart - b.innerStart);
  return nodes.filter(
    (node, i, all) =>
      !all.some(
        (other, j) =>
          j !== i && other.innerStart < node.innerStart && other.innerEnd > node.innerEnd,
      ),
  );
}

export function sanitizeDocumentsEditHtml(html: string): string {
  if (!html) return '';
  let next = html
    .replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[\s\S]*?<\/style>/gi, '')
    .replace(/<(iframe|object|embed|link|meta|img|video|audio|svg)\b[^>]*\/?>/gi, '')
    .replace(/<\/(iframe|object|embed|link|meta|img|video|audio|svg)>/gi, '')
    .replace(/\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
  next = next.replace(/<\/?([a-z][a-z0-9]*)\b[^>]*>/gi, (full, name: string) => {
    const tag = name.toLowerCase();
    if (tag === 'br') return '<br>';
    if (!SLIDES_EDIT_HTML_ALLOWED.has(tag)) return '';
    if (full.startsWith('</')) return `</${tag}>`;
    if (tag === 'a') {
      const href = /href\s*=\s*(["'])([^"']*)\1/i.exec(full)?.[2] || '';
      if (/^(https?:|\/|#|mailto:)/i.test(href) && !/^\s*javascript:/i.test(href)) {
        return `<a href="${href.replace(/"/g, '&quot;')}">`;
      }
      return '<a>';
    }
    return `<${tag}>`;
  });
  return next;
}

/** Snapshot of editable runs in source HTML, same paths the preview iframe posts. */
export function collectDocumentsTextEdits(html: string): DocumentsTextEdit[] {
  if (!html) return [];
  const edits: DocumentsTextEdit[] = [];
  let index = 0;
  while (true) {
    const section = extractSectionHtmlAt(html, index);
    if (!section) break;
    const counts = new Map<string, number>();
    for (const node of listEditableNodes(section)) {
      const nth = counts.get(node.tag) ?? 0;
      counts.set(node.tag, nth + 1);
      edits.push({ path: `${index}:${node.tag}:${nth}`, html: node.inner });
    }
    index += 1;
  }
  return edits;
}

function replaceSectionHtmlAt(html: string, index: number, sectionHtml: string): string {
  SECTION_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  let seen = 0;
  while ((match = SECTION_RE.exec(html))) {
    if (SLIDE_CLASS_RE.test(match[1] || '')) {
      if (seen === index) {
        return html.slice(0, match.index) + sectionHtml + html.slice(match.index + match[0].length);
      }
      seen += 1;
    }
  }
  return html;
}

function applyEditsToSection(sectionHtml: string, edits: DocumentsTextEdit[]): string {
  const nodes = listEditableNodes(sectionHtml);
  const counts = new Map<string, number>();
  const wanted = new Map<string, string>();
  for (const edit of edits) {
    const parsed = SLIDES_EDIT_PATH_RE.exec(edit.path);
    if (!parsed) continue;
    wanted.set(`${parsed[2]}:${parsed[3]}`, sanitizeDocumentsEditHtml(edit.html));
  }
  const replacements = nodes
    .map((node) => {
      const nth = counts.get(node.tag) ?? 0;
      counts.set(node.tag, nth + 1);
      const html = wanted.get(`${node.tag}:${nth}`);
      return html === undefined ? null : { ...node, html };
    })
    .filter((row): row is SectionsEditNode & { html: string } => row !== null)
    .sort((a, b) => b.innerStart - a.innerStart);
  let out = sectionHtml;
  for (const row of replacements) {
    out = out.slice(0, row.innerStart) + row.html + out.slice(row.innerEnd);
  }
  return out;
}

/**
 * Write Manual edit commits back onto the source document.html.
 * Does not persist inlined preview data-URLs: only tagged text runs change.
 */
export function applyDocumentsTextEdits(html: string, edits: DocumentsTextEdit[]): string {
  if (!html || !edits.length) return html;
  const bySection = new Map<number, DocumentsTextEdit[]>();
  for (const edit of edits) {
    const parsed = SLIDES_EDIT_PATH_RE.exec(edit.path);
    if (!parsed) continue;
    const index = Number(parsed[1]);
    const list = bySection.get(index) || [];
    list.push(edit);
    bySection.set(index, list);
  }
  let next = html;
  const indices = [...bySection.keys()].sort((a, b) => b - a);
  for (const index of indices) {
    const section = extractSectionHtmlAt(next, index);
    if (!section) continue;
    next = replaceSectionHtmlAt(next, index, applyEditsToSection(section, bySection.get(index) || []));
  }
  return next;
}
