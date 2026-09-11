import { describe, expect, it } from 'vitest';
import {
  clampSectionIndex,
  insertPageBreakHtml,
  parseDocumentsHeadingOutline,
  parseDocumentsOutline,
  parseDocumentsSectionOutline,
  sectionLayoutFromAttrs,
} from './documents-outline';

const SAMPLE = `<!DOCTYPE html><html><body>
<main class="document">
<section id="section-cover" class="section cover">
  <h1>Presentation Title &amp; Overview</h1>
</section>
<section class="section section-divider">
  <div class="divider-title">Context</div>
</section>
<section id="section-agenda" class="section" data-layout="content">
  <h1>Agenda</h1>
</section>
</main></body></html>`;

describe('parseDocumentsOutline', () => {
  it('lists headings in the prose flow', () => {
    const headings = parseDocumentsOutline(SAMPLE);
    expect(headings.map((row) => row.title)).toEqual([
      'Presentation Title & Overview',
      'Agenda',
    ]);
    expect(parseDocumentsSectionOutline(SAMPLE)).toHaveLength(3);
    expect(parseDocumentsHeadingOutline(SAMPLE)).toHaveLength(2);
  });

  it('inserts a page-break after a heading block', () => {
    const next = insertPageBreakHtml(SAMPLE, 0);
    expect(next).toContain('data-nexus-page-break');
    expect(next.indexOf('Presentation Title')).toBeLessThan(next.indexOf('data-nexus-page-break'));
  });

  it('returns an empty list for empty html', () => {
    expect(parseDocumentsOutline('')).toEqual([]);
  });

  it('uses h2 when a page block has no h1', () => {
    const html =
      '<main class="document"><section class="page cover"><h1>Document Title</h1></section><section class="page"><h2>Introduction</h2><p>Body</p></section></main>';
    const sections = parseDocumentsOutline(html);
    expect(sections).toHaveLength(2);
    expect(sections[0].title).toBe('Document Title');
    expect(sections[1].title).toBe('Introduction');
  });
});

describe('sectionLayoutFromAttrs', () => {
  it('prefers data-layout, then seed classes', () => {
    expect(sectionLayoutFromAttrs('class="section cover"')).toBe('cover');
    expect(sectionLayoutFromAttrs('data-layout="blank" class="section"')).toBe('content');
  });
});

describe('clampSectionIndex', () => {
  it('keeps the selection inside the outline', () => {
    expect(clampSectionIndex(4, 3)).toBe(2);
    expect(clampSectionIndex(-1, 3)).toBe(0);
    expect(clampSectionIndex(1, 0)).toBe(0);
  });
});
