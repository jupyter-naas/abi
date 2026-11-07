// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { sourceControlView } from './source-control';
import { MarkdownView, parseMarkdown, safeHref } from './source-control-markdown';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const render = async (node: ReactNode) => {
  mounted = await mount(() => createElement('div', null, node), {});
  return mounted.host;
};

const repo: ResourceEntry = {
  id: 'acme/site',
  name: 'site',
  kind: 'container',
  actions: ['delete'],
  size: null,
  modified: '2026-10-01T10:00:00Z',
  attributes: { visibility: 'private', default_branch: 'main', empty: 'no', description: 'The website' },
};

describe('source control view', () => {
  it('parses markdown blocks', () => {
    const blocks = parseMarkdown('# Title\n\nSome *text* here\nand more.\n\n- one\n- two\n\n```py\nprint(1)\n```\n\n> quoted\n\n---');
    expect(blocks.map((b) => b.kind)).toEqual(['heading', 'paragraph', 'list', 'code', 'quote', 'rule']);
    expect(blocks[1]).toEqual({ kind: 'paragraph', text: 'Some *text* here and more.' });
    expect(safeHref('javascript:alert(1)')).toBeNull();
    expect(safeHref('https://naas.ai')).toBe('https://naas.ai');
  });

  it('renders markdown safely', async () => {
    const host = await render(
      createElement(MarkdownView, {
        text: '# Readme\n\nUse `make up`, **then** [docs](https://docs.naas.ai) or [bad](javascript:alert(1)).',
      }),
    );

    expect(host.querySelector('h2')?.textContent).toBe('Readme');
    expect(host.querySelector('code')?.textContent).toBe('make up');
    expect(host.querySelector('strong')?.textContent).toBe('then');
    const links = [...host.querySelectorAll('a')];
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['https://docs.naas.ai']);
    expect(links[0].getAttribute('rel')).toContain('noopener');
    expect(host.textContent).toContain('bad');
  });

  it('shows repositories as cards with visibility and branch', async () => {
    const level = sourceControlView.level!(1, 'acme');
    const host = await render([sourceControlView.badges!(repo), level.card!(repo)]);

    expect(level.layout).toBe('cards');
    expect(host.textContent).toContain('private');
    expect(host.textContent).toContain('main');
    expect(host.textContent).toContain('The website');
    expect(sourceControlView.nounFor!(repo, 1).one).toBe('repository');
    expect(sourceControlView.deleteWarning!(repo)).toContain('whole history');
  });

  it('previews markdown files rendered and leaves code to the generic preview', async () => {
    const file = (name: string, text: string): ResourceDetail => ({
      entry: { id: `acme/site/${name}`, name, kind: 'item', actions: ['read'], size: text.length, modified: null, attributes: {} },
      content: { encoding: 'text', text, size: text.length, truncated: false },
    });
    const host = await render(sourceControlView.preview!(file('README.md', '## Hello'), {}));

    expect(host.querySelector('.data-md h3')?.textContent).toBe('Hello');
    expect(sourceControlView.preview!(file('app.py', 'print(1)'), {})).toBeNull();
    expect(sourceControlView.editor!.validateName!('../x')).not.toBeNull();
    expect(sourceControlView.editor!.validateName!('docs/notes.md')).toBeNull();
  });
});
