/** Canonical slide stage used by Zen / Nexus deck seeds. */
export const SLIDES_STAGE_WIDTH = 1280;
export const SLIDES_STAGE_HEIGHT = 720;

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
export const SLIDES_PREVIEW_FIT_STYLE_ID = 'zen-slides-preview-fit';

export function prepareSlidesPreviewHtml(html: string): string {
  if (!html) return html;
  if (html.includes(`id="${SLIDES_PREVIEW_FIT_STYLE_ID}"`)) return html;

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

  if (html.includes('</head>')) {
    return html.replace('</head>', `${inject}</head>`);
  }
  return `${inject}${html}`;
}
