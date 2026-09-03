import { describe, expect, it } from 'vitest';

import { isSlidesWriteTool } from './slides';

describe('isSlidesWriteTool', () => {
  it('treats deck writes and asset saves as slides writes', () => {
    expect(isSlidesWriteTool('write_slides_deck')).toBe(true);
    expect(isSlidesWriteTool('replace_in_slides_deck')).toBe(true);
    expect(isSlidesWriteTool('save_slides_asset')).toBe(true);
    expect(isSlidesWriteTool('save_slides_asset_from_url')).toBe(true);
    expect(isSlidesWriteTool('rename_slides_deck')).toBe(true);
    expect(isSlidesWriteTool('web_search')).toBe(false);
  });
});
