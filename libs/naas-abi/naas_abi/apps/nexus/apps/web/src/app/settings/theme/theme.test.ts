import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import ThemePage from './theme';
import { themeSections } from './theme-model';

describe('the Theme page', () => {
  it('renders every section of the kit', () => {
    const html = renderToString(createElement(ThemePage));
    for (const section of themeSections()) expect(html).toContain(`id="${section.id}"`);
    expect(html).toContain('role="tablist"');
    expect(html).toContain('role="toolbar"');
  });
});
