import { describe, expect, it } from 'vitest';
import {
  collectOfficeAssetRefs,
  inlineOfficeAssets,
  officeAssetApiPath,
  officeAssetFilename,
  rewriteOfficeAssetUrls,
} from './office-assets';
import { OFFICE_KINDS } from './office-kinds';

const DECK = `<img src="assets/img-001.png"><div style="background:url(assets/img-001.png)"></div>
<img src="./assets/logo.svg">`;

describe('collectOfficeAssetRefs', () => {
  it('dedupes relative assets/ refs', () => {
    expect(collectOfficeAssetRefs(DECK)).toEqual(['assets/img-001.png', './assets/logo.svg']);
  });

  it('ignores data-URLs and empty html', () => {
    expect(collectOfficeAssetRefs('')).toEqual([]);
    expect(collectOfficeAssetRefs('<img src="data:image/png;base64,AAAA">')).toEqual([]);
  });

  it('ignores absolute /assets/images URLs and directory prefixes', () => {
    const html = `
      <img src="https://cdn.example.com/assets/images/acme-logo.png">
      <img src="/assets/images/logo.png">
      <div style="background:url(assets/images)"></div>
      <img src="assets/img-001.png">
    `;
    expect(collectOfficeAssetRefs(html)).toEqual(['assets/img-001.png']);
  });
});

describe('rewriteOfficeAssetUrls', () => {
  it('rewrites each ref through the mapper', () => {
    const out = rewriteOfficeAssetUrls(DECK, (ref) => `https://cdn/${officeAssetFilename(ref)}`);
    expect(out).toContain('https://cdn/img-001.png');
    expect(out).toContain('https://cdn/logo.svg');
    expect(out).not.toContain('src="assets/');
  });
});

describe('inlineOfficeAssets', () => {
  it('walks the live html and inlines assets as data-URLs', async () => {
    const out = await inlineOfficeAssets(DECK, async (filename) => {
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
    const out = await inlineOfficeAssets('<img src="assets/missing.png">', async () => null);
    expect(out).toContain('assets/missing.png');
  });
});

describe.each(OFFICE_KINDS)('officeAssetApiPath ($id)', ({ id }) => {
  it('builds the served asset URL of the kind', () => {
    expect(officeAssetApiPath(id, 'pe-item', 'ws-1', 'img-001.png')).toBe(
      `/api/${id}/projects/pe-item/assets/img-001.png?workspace_id=ws-1`,
    );
  });
});
