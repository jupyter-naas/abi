import { describe, expect, it } from 'vitest';
import {
  collectSectionsAssetRefs,
  inlineSectionsAssets,
  rewriteSectionsAssetUrls,
  sectionsAssetApiPath,
  sectionsAssetFilename,
} from './documents-assets';

const DECK = `<img src="assets/img-001.png"><div style="background:url(assets/img-001.png)"></div>
<img src="./assets/logo.svg">`;

describe('collectSectionsAssetRefs', () => {
  it('dedupes relative assets/ refs', () => {
    expect(collectSectionsAssetRefs(DECK)).toEqual(['assets/img-001.png', './assets/logo.svg']);
  });

  it('ignores data-URLs and empty html', () => {
    expect(collectSectionsAssetRefs('')).toEqual([]);
    expect(collectSectionsAssetRefs('<img src="data:image/png;base64,AAAA">')).toEqual([]);
  });

  it('ignores absolute /assets/images URLs and directory prefixes', () => {
    const html = `
      <img src="https://cdn.example.com/assets/images/acme-logo.png">
      <img src="/assets/images/logo.png">
      <div style="background:url(assets/images)"></div>
      <img src="assets/img-001.png">
    `;
    expect(collectSectionsAssetRefs(html)).toEqual(['assets/img-001.png']);
  });
});

describe('rewriteSectionsAssetUrls', () => {
  it('rewrites each ref through the mapper', () => {
    const out = rewriteSectionsAssetUrls(DECK, (ref) => `https://cdn/${sectionsAssetFilename(ref)}`);
    expect(out).toContain('https://cdn/img-001.png');
    expect(out).toContain('https://cdn/logo.svg');
    expect(out).not.toContain('src="assets/');
  });
});

describe('inlineSectionsAssets', () => {
  it('walks the live html and inlines assets as data-URLs', async () => {
    const out = await inlineSectionsAssets(DECK, async (filename) => {
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
    const out = await inlineSectionsAssets('<img src="assets/missing.png">', async () => null);
    expect(out).toContain('assets/missing.png');
  });
});

describe('sectionsAssetApiPath', () => {
  it('builds the served sections-asset URL', () => {
    expect(sectionsAssetApiPath('pe-document', 'ws-1', 'img-001.png')).toBe(
      '/api/documents/projects/pe-document/assets/img-001.png?workspace_id=ws-1',
    );
  });
});
