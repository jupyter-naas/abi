import { describe, expect, it } from 'vitest';
import {
  clampSlideIndex,
  parseSheetsOutline,
  slideLayoutFromAttrs,
} from './sheets-outline';

const SAMPLE = `<!DOCTYPE html><html><body>
<main class="workbook">
<section id="slide-cover" class="slide cover">
  <h1>Workbook Title &amp; Overview</h1>
</section>
<section class="slide section-divider">
  <div class="divider-title">Context</div>
</section>
<section id="slide-agenda" class="slide" data-layout="content">
  <h1>Agenda</h1>
</section>
</main></body></html>`;

describe('parseSheetsOutline', () => {
  it('lists sections with id, title, and layout', () => {
    const sheets = parseSheetsOutline(SAMPLE);
    expect(sheets).toHaveLength(3);
    expect(sheets[0]).toEqual({
      index: 0,
      id: 'slide-cover',
      title: 'Workbook Title & Overview',
      layout: 'cover',
    });
    expect(sheets[1].title).toBe('Context');
    expect(sheets[1].layout).toBe('section-divider');
    expect(sheets[2].id).toBe('slide-agenda');
    expect(sheets[2].layout).toBe('content');
  });

  it('returns an empty list for empty html', () => {
    expect(parseSheetsOutline('')).toEqual([]);
  });
});

describe('slideLayoutFromAttrs', () => {
  it('prefers data-layout, then seed classes', () => {
    expect(slideLayoutFromAttrs('class="slide cover"')).toBe('cover');
    expect(slideLayoutFromAttrs('data-layout="blank" class="slide"')).toBe('content');
  });
});

describe('clampSlideIndex', () => {
  it('keeps the selection inside the filmstrip', () => {
    expect(clampSlideIndex(4, 3)).toBe(2);
    expect(clampSlideIndex(-1, 3)).toBe(0);
    expect(clampSlideIndex(1, 0)).toBe(0);
  });
});
