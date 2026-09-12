import {
  SLIDES_PDF_FROM_DOM_SCRIPT,
  SLIDES_PDF_FROM_DOM_SCRIPT_ID,
} from './documents-pptx-from-dom';

/** Letter content width (8.5in at 96dpi). Reading column, not a 16:9 stage. */
export const DOCUMENTS_PAGE_WIDTH = 816;
/** Letter page height at 96dpi. Soft pagination fills this sheet. */
export const DOCUMENTS_PAGE_MIN_HEIGHT = 1056;
export const DOCUMENTS_PAGE_PADDING_TOP = 72;
export const DOCUMENTS_PAGE_PADDING_X = 80;
export const DOCUMENTS_PAGE_PADDING_BOTTOM = 96;
/** Gap between stacked letter sheets in the preview (Word / Docs print layout). */
export const DOCUMENTS_PAGE_GAP_PX = 32;
export const DOCUMENTS_PAGE_CONTENT_HEIGHT =
  DOCUMENTS_PAGE_MIN_HEIGHT - DOCUMENTS_PAGE_PADDING_TOP - DOCUMENTS_PAGE_PADDING_BOTTOM;
export const DOCUMENTS_PREVIEW_GUTTER_PX = 48;

/** Hard page break in source HTML. Print and the paginator honor this, not a section. */
export const PAGE_BREAK_HTML = '<div class="page-break" data-nexus-page-break></div>';

export type DocumentsFlowBlock = {
  height: number;
  hardBreak: boolean;
};

/**
 * Group flow blocks into letter pages. A hard break is ODF fo:break-before=page
 * / Google Docs PageBreak / Word w:br w:type="page": start a new sheet, same section.
 */
export function planLetterPages(
  blocks: DocumentsFlowBlock[],
  contentHeight = DOCUMENTS_PAGE_CONTENT_HEIGHT,
): number[][] {
  if (!blocks.length) return [[]];
  const pages: number[][] = [[]];
  let used = 0;
  blocks.forEach((block, index) => {
    if (block.hardBreak) {
      if (pages[pages.length - 1].length) {
        pages.push([]);
        used = 0;
      }
      return;
    }
    const height = Math.max(0, block.height);
    const current = pages[pages.length - 1];
    if (!current.length) {
      current.push(index);
      used = height;
      return;
    }
    if (contentHeight > 0 && used + height > contentHeight) {
      pages.push([index]);
      used = height;
      return;
    }
    current.push(index);
    used += height;
  });
  if (pages.length > 1 && pages[pages.length - 1].length === 0) {
    pages.pop();
  }
  return pages;
}

/** True when a flow run has something other than a hard page-break to paint. */
export function letterRunHasContent(blocks: DocumentsFlowBlock[]): boolean {
  return blocks.some((block) => !block.hardBreak);
}

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
  function headingNodes() {
    return Array.prototype.slice.call(
      document.querySelectorAll('.letter-page h1, .letter-page h2, .letter-page h3, main.document > section h1, main.document > section h2, main.document > section h3')
    );
  }
  function isPageBreak(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.getAttribute && el.getAttribute('data-nexus-page-break') != null) return true;
    return !!(el.classList && el.classList.contains('page-break'));
  }
  function isLetterPage(el) {
    return !!(el && el.nodeType === 1 && el.classList && el.classList.contains('letter-page'));
  }
  function meaningfulNode(n) {
    if (!n) return false;
    if (n.nodeType === 1) return true;
    if (n.nodeType === 3) return /\\S/.test(n.textContent || '');
    return false;
  }
  function makeLetterPage() {
    var el = document.createElement('div');
    el.className = 'letter-page';
    el.setAttribute('data-nexus-letter-page', '');
    return el;
  }
  function isDocHeader(el) {
    return !!(el && el.nodeType === 1 && (
      (el.classList && el.classList.contains('doc-header')) ||
      (el.tagName === 'HEADER' && !(el.classList && el.classList.contains('doc-footer'))) ||
      (el.classList && (el.classList.contains('brand-logo') || el.classList.contains('wordmark')))
    ));
  }
  function isDocFooter(el) {
    return !!(el && el.nodeType === 1 && (
      (el.classList && el.classList.contains('doc-footer')) ||
      el.tagName === 'FOOTER'
    ));
  }
  function isHardBreak(el) {
    if (isPageBreak(el)) return true;
    if (!el || el.nodeType !== 1) return false;
    try {
      var style = window.getComputedStyle(el);
      var before = String(style.breakBefore || style.pageBreakBefore || '').toLowerCase();
      return before === 'page' || before === 'always';
    } catch (e) {
      return false;
    }
  }
  function bodyOverflows(bodyEl) {
    return !!(bodyEl && bodyEl.scrollHeight > bodyEl.clientHeight + 1);
  }
  function nodeHasBodyContent(n) {
    if (!n) return false;
    if (n.nodeType === 3) return /\\S/.test(n.textContent || '');
    if (n.nodeType !== 1) return false;
    if (isPageBreak(n) || isHardBreak(n)) return false;
    if (isDocHeader(n) || isDocFooter(n) || isChromeClone(n)) return false;
    if (n.querySelector && n.querySelector('img, canvas, video, svg')) return true;
    return /\\S/.test(n.textContent || '');
  }
  function bodyHasContent(bodyEl) {
    if (!bodyEl) return false;
    return Array.prototype.slice.call(bodyEl.childNodes).some(nodeHasBodyContent);
  }
  function runHasContent(run) {
    return !!(run && run.nodes && run.nodes.some(nodeHasBodyContent));
  }
  function discardEmptyPage(page, bodyEl) {
    if (page && page.parentNode && !bodyHasContent(bodyEl)) {
      page.parentNode.removeChild(page);
      return true;
    }
    return false;
  }
  function isChromeClone(el) {
    return !!(el && el.getAttribute && el.getAttribute('data-nexus-chrome-clone') != null);
  }
  function cloneChrome(node) {
    if (!node) return null;
    var copy = node.cloneNode(true);
    if (copy.setAttribute) copy.setAttribute('data-nexus-chrome-clone', '');
    return copy;
  }
  function decorateLetterPage(page, header, footer, clone) {
    var body = document.createElement('div');
    body.className = 'doc-body';
    if (header) page.appendChild(clone ? cloneChrome(header) : header);
    page.appendChild(body);
    if (footer) page.appendChild(clone ? cloneChrome(footer) : footer);
    return body;
  }
  function collectRuns(root) {
    var runs = [];
    var current = { header: null, footer: null, nodes: [] };
    function flush() {
      if (current.header || current.footer || current.nodes.length) {
        runs.push(current);
        current = { header: null, footer: null, nodes: [] };
      }
    }
    function takeKids(parent) {
      Array.prototype.slice.call(parent.childNodes).forEach(absorb);
    }
    function absorb(n) {
      if (!meaningfulNode(n)) return;
      if (isLetterPage(n)) {
        takeKids(n);
        return;
      }
      if (n.nodeType === 1 && n.matches && n.matches('section.page, section.section')) {
        flush();
        takeKids(n);
        flush();
        return;
      }
      if (isChromeClone(n)) return;
      if (isPageBreak(n)) {
        current.nodes.push(n);
        return;
      }
      if (isDocHeader(n)) {
        var pendingContent = current.nodes.some(function (x) { return !isPageBreak(x); });
        if (current.header || current.footer || pendingContent) flush();
        else current.nodes = [];
        current.header = n;
        return;
      }
      if (isDocFooter(n)) {
        current.footer = n;
        return;
      }
      if (n.nodeType === 1 && n.classList && n.classList.contains('doc-body')) {
        takeKids(n);
        return;
      }
      current.nodes.push(n);
    }
    Array.prototype.slice.call(root.childNodes).forEach(absorb);
    flush();
    return runs;
  }
  function paginateDocument() {
    var root = document.querySelector('main.document, .document');
    if (!root) return;
    tagEditTargets();
    var runs = collectRuns(root);
    if (!runs.length) return;
    var holders = sectionNodes();
    while (root.firstChild) root.removeChild(root.firstChild);
    runs.forEach(function (run) {
      if (!runHasContent(run)) return;
      var page = makeLetterPage();
      root.appendChild(page);
      var bodyEl = decorateLetterPage(page, run.header, run.footer, false);
      var filled = false;
      run.nodes.forEach(function (node) {
        if (isHardBreak(node)) {
          if (filled) {
            page = makeLetterPage();
            root.appendChild(page);
            bodyEl = decorateLetterPage(page, run.header, run.footer, true);
            filled = false;
          }
          return;
        }
        bodyEl.appendChild(node);
        filled = true;
        if (bodyEl.childNodes.length > 1 && bodyOverflows(bodyEl)) {
          bodyEl.removeChild(node);
          if (discardEmptyPage(page, bodyEl)) {
            page = null;
            bodyEl = null;
          }
          page = makeLetterPage();
          root.appendChild(page);
          bodyEl = decorateLetterPage(page, run.header, run.footer, true);
          bodyEl.appendChild(node);
        }
      });
      discardEmptyPage(page, bodyEl);
    });
    holders.forEach(function (sec) {
      if (!sec.parentNode) {
        sec.setAttribute('data-nexus-empty-section', '');
        sec.style.display = 'none';
        root.appendChild(sec);
      }
    });
    root.setAttribute('data-nexus-paginated', '1');
  }
  function measureHeight() {
    var body = document.body;
    var el = document.documentElement;
    var pages = document.querySelectorAll('.letter-page');
    var stacked = 0;
    if (pages.length) {
      stacked = pages.length * PAGE_MIN_HEIGHT + Math.max(0, pages.length - 1) * ${DOCUMENTS_PAGE_GAP_PX};
    }
    var measured = Math.max(
      stacked,
      (body && body.scrollHeight) || 0,
      (body && body.offsetHeight) || 0,
      (el && el.scrollHeight) || 0,
      (el && el.offsetHeight) || 0,
      PAGE_MIN_HEIGHT
    );
    return measured;
  }
  function outlineTops() {
    var heads = headingNodes();
    if (heads.length) {
      return heads.map(function (node) { return node.offsetTop || 0; });
    }
    return sectionNodes().map(function (node) { return node.offsetTop || 0; });
  }
  function reportMetrics() {
    try {
      parent.postMessage(
        {
          source: SOURCE,
          type: 'metrics',
          height: measureHeight(),
          sectionTops: outlineTops(),
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
    paginateDocument();
    parent.postMessage(
      { source: SOURCE, type: 'ready', height: measureHeight() },
      '*'
    );
    reportMetrics();
    setTimeout(reportMetrics, 50);
    setTimeout(reportMetrics, 250);
    waitForImages().then(function () {
      paginateDocument();
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
    var existing = document.querySelectorAll('[' + EDIT_ATTR + ']');
    if (existing.length) return Array.prototype.slice.call(existing);
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

/** Print: each letter sheet is one page. Hard .page-break markers still force a page. */
export const SLIDES_PREVIEW_PRINT_CSS = `
  @media print {
    @page { size: letter; margin: 0; }
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
      background: transparent !important;
      transform: none !important;
      zoom: 1 !important;
      overflow: visible !important;
    }
    .letter-page {
      position: relative !important;
      display: flex !important;
      flex-direction: column !important;
      width: 8.5in !important;
      height: 11in !important;
      min-height: 11in !important;
      max-height: 11in !important;
      margin: 0 !important;
      padding: 0.3in 0.5in !important;
      overflow: hidden !important;
      box-shadow: none !important;
      border: none !important;
      background: #fff !important;
      page-break-after: always !important;
      break-after: page !important;
      page-break-inside: avoid !important;
      break-inside: avoid !important;
    }
    .letter-page:last-of-type {
      page-break-after: auto !important;
      break-after: auto !important;
    }
    .letter-page > .doc-header {
      position: static !important;
      top: auto !important;
      right: auto !important;
      left: auto !important;
      flex: 0 0 auto !important;
      align-self: flex-end !important;
      margin: 0 0 12pt !important;
    }
    .letter-page > .doc-body {
      flex: 1 1 auto !important;
      min-height: 0 !important;
      overflow: hidden !important;
    }
    .letter-page > .doc-footer {
      position: static !important;
      left: auto !important;
      right: auto !important;
      bottom: auto !important;
      flex: 0 0 auto !important;
      margin: 12pt 0 0 !important;
    }
    .letter-page > .doc-footer ~ .doc-header,
    .letter-page > .doc-footer .brand-logo,
    .letter-page > .doc-footer .wordmark {
      display: none !important;
    }
    .page-break, [data-nexus-page-break] {
      display: block !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      page-break-before: always !important;
      break-before: page !important;
    }
    .letter-page .page-break,
    .letter-page [data-nexus-page-break] {
      page-break-before: auto !important;
      break-before: auto !important;
    }
    .page[data-nexus-empty-section],
    .section[data-nexus-empty-section] {
      display: none !important;
    }
    .page, .section {
      display: block !important;
      position: relative !important;
      width: auto !important;
      height: auto !important;
      min-height: 0 !important;
      max-width: none !important;
      max-height: none !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: visible !important;
      contain: none !important;
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
    padding: ${DOCUMENTS_PAGE_PADDING_TOP}px ${DOCUMENTS_PAGE_PADDING_X}px ${DOCUMENTS_PAGE_PADDING_BOTTOM}px !important;
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
  .document[data-nexus-paginated="1"] {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    gap: ${DOCUMENTS_PAGE_GAP_PX}px !important;
    padding: 0 0 8px !important;
    min-height: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    counter-reset: fm-page;
  }
  .document[data-nexus-paginated="1"] > .page,
  .document[data-nexus-paginated="1"] > .section {
    counter-increment: none !important;
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
  .document[data-nexus-paginated="1"] > .page,
  .document[data-nexus-paginated="1"] > .section {
    display: none !important;
    margin: 0 !important;
  }
  .letter-page {
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
    box-sizing: border-box !important;
    width: ${DOCUMENTS_PAGE_WIDTH}px !important;
    height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    min-height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    max-height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    padding: 28px ${DOCUMENTS_PAGE_PADDING_X}px !important;
    margin: 0 !important;
    border: none !important;
    background: #fff !important;
    box-shadow: 0 1px 3px rgba(26, 26, 26, 0.10), 0 12px 32px rgba(26, 26, 26, 0.12) !important;
    overflow: hidden !important;
    flex-shrink: 0 !important;
    counter-increment: fm-page;
  }
  .letter-page > .doc-header {
    position: static !important;
    top: auto !important;
    right: auto !important;
    left: auto !important;
    bottom: auto !important;
    z-index: 2 !important;
    display: flex !important;
    justify-content: flex-end !important;
    align-items: flex-start !important;
    align-self: flex-end !important;
    margin: 0 0 16px !important;
    flex: 0 0 auto !important;
  }
  .letter-page > .doc-body {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow: hidden !important;
  }
  .letter-page > .doc-footer {
    position: static !important;
    left: auto !important;
    right: auto !important;
    top: auto !important;
    bottom: auto !important;
    z-index: 2 !important;
    margin: 16px 0 0 !important;
    flex: 0 0 auto !important;
  }
  .letter-page .brand-logo,
  .letter-page .wordmark {
    display: block !important;
    width: 118px !important;
    max-width: 118px !important;
    height: auto !important;
    max-height: 50px !important;
    flex: 0 0 auto !important;
  }
  .letter-page > .doc-footer .brand-logo,
  .letter-page > .doc-footer .wordmark,
  .letter-page > .doc-footer svg,
  .letter-page > .doc-footer ~ .doc-header,
  .letter-page > .doc-footer ~ .brand-logo,
  .letter-page > .doc-footer ~ .wordmark,
  .letter-page > .doc-footer ~ svg {
    display: none !important;
  }
  .page-break, [data-nexus-page-break] {
    display: block !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    visibility: hidden !important;
    page-break-before: always !important;
    break-before: page !important;
  }
  .letter-page .page-break,
  .letter-page [data-nexus-page-break] {
    page-break-before: auto !important;
    break-before: auto !important;
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
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
    width: auto !important;
    height: auto !important;
    min-height: ${DOCUMENTS_PAGE_MIN_HEIGHT}px !important;
    margin: 0 !important;
    padding: 88px 64px 56px !important;
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
