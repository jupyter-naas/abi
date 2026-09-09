import { describe, expect, it } from 'vitest';
import {
  collectSlidesAssetRefs,
  inlineSlidesAssets,
  rewriteSlidesAssetUrls,
  slidesAssetApiPath,
  slidesAssetFilename,
} from './slides-assets';

const DECK = `<img src="assets/img-001.png"><div style="background:url(assets/img-001.png)"></div>
<img src="./assets/logo.svg">`;

describe('collectSlidesAssetRefs', () => {
  it('dedupes relative assets/ refs', () => {
    expect(collectSlidesAssetRefs(DECK)).toEqual(['assets/img-001.png', './assets/logo.svg']);
  });

  it('ignores data-URLs and empty html', () => {
    expect(collectSlidesAssetRefs('')).toEqual([]);
    expect(collectSlidesAssetRefs('<img src="data:image/png;base64,AAAA">')).toEqual([]);
  });
});

describe('rewriteSlidesAssetUrls', () => {
  it('rewrites each ref through the mapper', () => {
    const out = rewriteSlidesAssetUrls(DECK, (ref) => `https://cdn/${slidesAssetFilename(ref)}`);
    expect(out).toContain('https://cdn/img-001.png');
    expect(out).toContain('https://cdn/logo.svg');
    expect(out).not.toContain('src="assets/');
  });
});

describe('inlineSlidesAssets', () => {
  it('walks the live html and inlines assets as data-URLs', async () => {
    const out = await inlineSlidesAssets(DECK, async (filename) => {
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
    const out = await inlineSlidesAssets('<img src="assets/missing.png">', async () => null);
    expect(out).toContain('assets/missing.png');
  });
});

describe('slidesAssetApiPath', () => {
  it('builds the served slides-asset URL', () => {
    expect(slidesAssetApiPath('pe-deck', 'ws-1', 'img-001.png')).toBe(
      '/api/slides/projects/pe-deck/assets/img-001.png?workspace_id=ws-1',
    );
  });
});
