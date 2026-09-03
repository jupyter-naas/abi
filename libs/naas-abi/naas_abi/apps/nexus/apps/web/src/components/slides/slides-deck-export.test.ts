import { describe, expect, it } from 'vitest';
import {
  deckExportFilename,
  deckHtmlToMarkdown,
  deckHtmlToPlainText,
  injectPrintStyles,
  sanitizeDeckFilename,
} from './slides-deck-export';

const FIXTURE = `<!doctype html>
<html><head><style>:root { --panel: #fff; }</style></head>
<body><main class="deck">
<section class="slide cover"><h1>Q3 Review</h1><p class="subtitle">Exec readout</p></section>
<section class="slide"><div class="eyebrow">Context</div><h1>Why now</h1><p>Market shifted.</p></section>
</main></body></html>`;

describe('sanitizeDeckFilename', () => {
  it('slugifies titles as snake_case', () => {
    expect(sanitizeDeckFilename('Q3 Review')).toBe('q3_review');
    expect(sanitizeDeckFilename('   ')).toBe('presentation');
  });
});

describe('deckHtmlToMarkdown', () => {
  it('exports slide structure from HTML', () => {
    const md = deckHtmlToMarkdown(FIXTURE, 'Board deck');
    expect(md).toContain('# Board deck');
    expect(md).toContain('## Slide 1 — Cover: Q3 Review');
    expect(md).toContain('### Q3 Review');
    expect(md).toContain('Exec readout');
    expect(md).toContain('## Slide 2 — Content: Why now');
    expect(md).toContain('Market shifted.');
  });
});

describe('deckHtmlToPlainText', () => {
  it('exports readable plain text blocks', () => {
    const txt = deckHtmlToPlainText(FIXTURE, 'Board deck');
    expect(txt).toContain('Board deck');
    expect(txt).toContain('Q3 Review');
    expect(txt).toContain('Why now');
    expect(txt).toContain('Market shifted.');
  });
});

describe('deckExportFilename', () => {
  it('builds download names with .slides.html for HTML', () => {
    expect(deckExportFilename('Q3 Review', 'md')).toBe('q3_review.md');
    expect(deckExportFilename('Forensic Analysis', 'html')).toBe(
      'forensic_analysis.slides.html',
    );
  });
});

describe('injectPrintStyles', () => {
  it('adds print CSS before </head>', () => {
    const out = injectPrintStyles(FIXTURE);
    expect(out).toContain('nexus-slides-print');
    expect(out).toContain('@page');
  });
});
