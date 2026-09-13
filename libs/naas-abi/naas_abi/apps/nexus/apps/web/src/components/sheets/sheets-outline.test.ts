import { describe, expect, it } from 'vitest';
import { clampSlideIndex, parseSheetsOutline, slideLayoutFromAttrs } from './sheets-outline';

const SAMPLE = `<!doctype html><html><head>
<script type="application/vnd.nexus.sheet+json">
{"title":"Budget","sheets":[{"name":"Revenue","rows":[]},{"name":"Costs","rows":[]}]}
</script></head><body></body></html>`;

describe('parseSheetsOutline', () => {
  it('lists workbook tabs from the JSON block', () => {
    const tabs = parseSheetsOutline(SAMPLE);
    expect(tabs).toHaveLength(2);
    expect(tabs[0]).toEqual({
      index: 0,
      id: null,
      title: 'Revenue',
      layout: 'content',
    });
    expect(tabs[1].title).toBe('Costs');
  });

  it('returns an empty list for empty html', () => {
    expect(parseSheetsOutline('')).toEqual([]);
  });
});

describe('slideLayoutFromAttrs', () => {
  it('always returns content for sheet tabs', () => {
    expect(slideLayoutFromAttrs('class="slide cover"')).toBe('content');
  });
});

describe('clampSlideIndex', () => {
  it('keeps the selection inside the filmstrip', () => {
    expect(clampSlideIndex(4, 3)).toBe(2);
    expect(clampSlideIndex(-1, 3)).toBe(0);
    expect(clampSlideIndex(1, 0)).toBe(0);
  });
});
