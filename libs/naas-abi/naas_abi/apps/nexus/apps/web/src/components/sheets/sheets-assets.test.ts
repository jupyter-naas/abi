import { describe, expect, it } from 'vitest';
import {
  collectSheetsAssetRefs,
  inlineSheetsAssets,
  rewriteSheetsAssetUrls,
  sheetsAssetApiPath,
  sheetsAssetFilename,
} from './sheets-assets';

const DECK = `<img src="assets/img-001.png"><div style="background:url(assets/img-001.png)"></div>
<img src="./assets/logo.svg">`;

describe('collectSheetsAssetRefs', () => {
  it('dedupes relative assets/ refs', () => {
    expect(collectSheetsAssetRefs(DECK)).toEqual(['assets/img-001.png', './assets/logo.svg']);
  });

  it('ignores data-URLs and empty html', () => {
    expect(collectSheetsAssetRefs('')).toEqual([]);
    expect(collectSheetsAssetRefs('<img src="data:image/png;base64,AAAA">')).toEqual([]);
  });

  it('ignores absolute /assets/images URLs and directory prefixes', () => {
    const html = `
      <img src="https://cdn.example.com/assets/images/acme-logo.png">
      <img src="/assets/images/logo.png">
      <div style="background:url(assets/images)"></div>
      <img src="assets/img-001.png">
    `;
    expect(collectSheetsAssetRefs(html)).toEqual(['assets/img-001.png']);
  });
});

describe('rewriteSheetsAssetUrls', () => {
  it('rewrites each ref through the mapper', () => {
    const out = rewriteSheetsAssetUrls(DECK, (ref) => `https://cdn/${sheetsAssetFilename(ref)}`);
    expect(out).toContain('https://cdn/img-001.png');
    expect(out).toContain('https://cdn/logo.svg');
    expect(out).not.toContain('src="assets/');
  });
});

describe('inlineSheetsAssets', () => {
  it('walks the live html and inlines assets as data-URLs', async () => {
    const out = await inlineSheetsAssets(DECK, async (filename) => {
      if (filename === 'img-001.png') return 'data:image/png;base64,AAA';
      if (filename === 'logo.svg') return 'data:image/svg+xml;base64,BBB';
      return null;
    });
    expect(out).toContain('src="data:image/png;base64,AAA"');
    expect(out).toContain('url(data:image/png;base64,AAA)');
    expect(out).toContain('src="data:image/svg+xml;base64,BBB"');
    expect(out).not.toContain('assets/');
  });

  it('keeps the ref when the loader misses', async () => {
    const out = await inlineSheetsAssets('<img src="assets/missing.png">', async () => null);
    expect(out).toContain('assets/missing.png');
  });
});

describe('sheetsAssetApiPath', () => {
  it('builds the served sheets-asset URL', () => {
    expect(sheetsAssetApiPath('pe-workbook', 'ws-1', 'img-001.png')).toBe(
      '/api/sheets/projects/pe-workbook/assets/img-001.png?workspace_id=ws-1',
    );
  });
});
