import { describe, expect, it } from 'vitest';
import { clampTabIndex, parseWorkbookTabs } from './sheets-outline';

const SAMPLE = `<!doctype html><html><head>
<script type="application/vnd.nexus.sheet+json">
{"title":"Budget","sheets":[{"name":"Revenue","rows":[]},{"name":"Costs","rows":[]}]}
</script></head><body></body></html>`;

describe('parseWorkbookTabs', () => {
  it('lists workbook tabs from the JSON block', () => {
    const tabs = parseWorkbookTabs(SAMPLE);
    expect(tabs).toHaveLength(2);
    expect(tabs[0]).toEqual({
      index: 0,
      id: null,
      title: 'Revenue',
    });
    expect(tabs[1].title).toBe('Costs');
  });

  it('returns an empty list for empty html', () => {
    expect(parseWorkbookTabs('')).toEqual([]);
  });
});

describe('clampTabIndex', () => {
  it('keeps the selection inside the tab strip', () => {
    expect(clampTabIndex(4, 3)).toBe(2);
    expect(clampTabIndex(-1, 3)).toBe(0);
    expect(clampTabIndex(1, 0)).toBe(0);
  });
});
