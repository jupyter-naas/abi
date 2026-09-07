/** Canonical slide stage used by Nexus deck seeds. */
export const SLIDES_STAGE_WIDTH = 1280;
export const SLIDES_STAGE_HEIGHT = 720;

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
      type: 'export-pptx-result';
      ok: boolean;
      error?: string;
    };

export type SlidesPreviewFromParentMessage = {
  source: typeof SLIDES_PREVIEW_MESSAGE_SOURCE;
  type: 'export-pptx';
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
    if (!data || data.source !== SOURCE || data.type !== 'export-pptx') return;
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
  window.addEventListener('load', reportMetrics);
  if (typeof ResizeObserver !== 'undefined') {
    try {
      new ResizeObserver(reportMetrics).observe(document.documentElement);
    } catch (e) {}
  }
})();
</script>`;

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
  }
</style>`;
    if (next.includes('</head>')) {
      next = next.replace('</head>', `${inject}</head>`);
    } else {
      next = `${inject}${next}`;
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
