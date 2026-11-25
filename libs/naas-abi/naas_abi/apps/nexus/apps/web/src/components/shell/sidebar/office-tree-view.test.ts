/**
 * The Documents, Sheets and Slides sidebar trees are file explorers, so this pins
 * the parts a redesign keeps breaking:
 *
 *   - no section banners, only folders and files;
 *   - items are anchors into the app, so cmd-click and middle-click work and a
 *     plain click keeps the workspace shell and the chat pane;
 *   - the item being edited is shown by selection, not by a header;
 *   - items carry the name Abi generated from the topic.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

import { OFFICE_KINDS } from '@/components/office/office-kinds';
import { OfficeTreeView } from './office-tree-view';
import { buildOfficeTree, type OfficeProjectTree } from './office-tree';

describe.each(OFFICE_KINDS)('OfficeTreeView ($id)', (kind) => {
  const id = kind.id;
  const dir = `${id}/ws/materiaux`;
  const itemTree: OfficeProjectTree = {
    slug: 'materiaux',
    root: dir,
    entries: [
      { name: kind.fileName, path: `${dir}/${kind.fileName}`, type: 'file' },
      { name: 'project.json', path: `${dir}/project.json`, type: 'file' },
      { name: 'assets', path: `${dir}/assets`, type: 'dir' },
    ],
    assets: [{ name: 'logo.png', path: `${dir}/assets/logo.png`, type: 'file' }],
  };

  const items = buildOfficeTree(
    kind,
    [
      { slug: 'materiaux', title: 'Matériaux de construction' },
      { slug: 'ai-news', title: 'Latest Ai News 2' },
    ],
    { workspaceId: 'ws-1', openSlug: 'materiaux', trees: { materiaux: itemTree } },
  );

  function markup(props: Record<string, unknown> = {}): string {
    return renderToStaticMarkup(
      createElement(OfficeTreeView, {
        kind,
        items,
        rootHref: `/workspace/ws-1/${id}`,
        currentPath: `/workspace/ws-1/${id}/materiaux`,
        rootExpanded: true,
        onToggleRoot: () => {},
        expandedItems: ['materiaux'],
        onToggleItem: () => {},
        expandedDirs: [],
        onToggleDir: () => {},
        onOpenItem: () => {},
        ...props,
      } as never),
    );
  }

  const itemRows = (html: string) =>
    html.match(new RegExp(`<a[^>]*data-testid="${kind.itemTestId}"[^>]*>`, 'g')) ?? [];

  it('has no editorial section headers', () => {
    const html = markup();
    for (const banner of ['OPEN PRESENTATION', 'Open presentation', 'Open document', 'TEMPLATES', 'Templates', 'All projects']) {
      expect(html).not.toContain(banner);
    }
  });

  it('shows one root folder holding the items', () => {
    const html = markup();
    expect(html).toContain(`>${kind.treeRootLabel}</span>`);
    expect((html.match(new RegExp(`data-testid="${id}-tree-root"`, 'g')) ?? []).length).toBe(1);
  });

  it('lists items by the name Abi generated', () => {
    const html = markup();
    expect(html).toContain('Matériaux de construction');
    expect(html).toContain('Latest Ai News 2');
  });

  it('links items into the app instead of a new window', () => {
    const html = markup();
    expect(html).toContain(`href="/workspace/ws-1/${id}/materiaux"`);
    expect(html).toContain(`href="/workspace/ws-1/${id}/ai-news"`);
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('keeps items as anchors so cmd-click and middle-click still work', () => {
    expect(itemRows(markup()).length).toBe(2);
  });

  it('marks the open item as the current page', () => {
    const html = markup();
    expect(html).toMatch(/data-slug="materiaux"[^>]*aria-current="page"|aria-current="page"[^>]*data-slug="materiaux"/);
    expect((html.match(/aria-current="page"/g) ?? []).length).toBe(1);
  });

  it('does not claim an item is the current page from the index', () => {
    const html = markup({ currentPath: `/workspace/ws-1/${id}` });
    expect(itemRows(html).some((row) => row.includes('aria-current'))).toBe(false);
    // The last item opened still reads as selected, the way an editor keeps
    // showing which file you were in.
    expect(html).toContain('bg-workspace-accent-15');
  });

  it(`puts ${kind.allRowLabel} first and marks it current on the gallery`, () => {
    const html = markup({ currentPath: `/workspace/ws-1/${id}` });
    expect(html).toContain(`>${kind.allRowLabel}</span>`);
    expect(html.indexOf(`${id}-tree-all`)).toBeLessThan(html.indexOf(`${id}-tree-root`));
    expect(html).toMatch(
      new RegExp(`data-testid="${id}-tree-all"[^>]*aria-current="page"|aria-current="page"[^>]*data-testid="${id}-tree-all"`),
    );
    expect(html).toContain(`href="/workspace/ws-1/${id}"`);
  });

  it(`does not highlight ${kind.allRowLabel} on an open item`, () => {
    const all = markup().match(new RegExp(`<a[^>]*data-testid="${id}-tree-all"[^>]*>`, 'g')) ?? [];
    expect(all.length).toBe(1);
    expect(all[0]).not.toContain('aria-current');
  });

  it('shows selection on the open item and not on the others', () => {
    const rows = itemRows(markup());
    const selected = rows.filter((row) => row.includes('bg-workspace-accent-15'));
    expect(rows.length).toBe(2);
    expect(selected.length).toBe(1);
    expect(selected[0]).toContain('data-slug="materiaux"');
  });

  it('expands the open item to the files that exist on disk', () => {
    const html = markup();
    expect(html).toContain(kind.fileName);
    expect(html).toContain('project.json');
    expect(html).toContain('>assets</span>');
  });

  it('leaves a collapsed item unexpanded', () => {
    expect(markup({ expandedItems: [] })).not.toContain('project.json');
  });

  it('hides the whole tree when the root is collapsed', () => {
    const html = markup({ rootExpanded: false });
    expect(html).not.toContain('Matériaux de construction');
    expect(html).toContain(`>${kind.treeRootLabel}</span>`);
  });

  it('gives every folder a real disclosure button', () => {
    const html = markup();
    expect(html).toContain(`aria-label="Collapse ${kind.treeRootLabel}"`);
    expect(html).toContain('aria-label="Collapse Matériaux de construction"');
    expect(html).toContain('aria-label="Expand Latest Ai News 2"');
    expect(html).toContain('aria-label="Expand assets"');
  });

  it('nests a fetched asset under the assets folder once opened', () => {
    expect(markup()).not.toContain('logo.png');
    expect(markup({ expandedDirs: [`${dir}/assets`] })).toContain('logo.png');
  });

  it(`routes ${kind.fileName} to its item`, () => {
    expect(markup()).toMatch(
      new RegExp(`<a[^>]*href="/workspace/ws-1/${id}/materiaux"[^>]*data-testid="${id}-tree-file"`),
    );
  });

  it('says so when the workspace has no item yet', () => {
    expect(markup({ items: [] })).toContain(kind.emptyLabel);
  });

  it('puts Rename and Archive on an item row when the chat actions are wired', () => {
    const html = markup({
      onStartRename: () => {},
      onRename: () => {},
      onCancelRename: () => {},
      onArchive: () => {},
    });
    expect(html).toContain(`data-testid="${id}-project-menu"`);
  });

  it('lists archived items without a second root', () => {
    const html = markup({ hideRoot: true, emptyLabel: kind.archivedEmptyLabel });
    expect(html).toContain(`data-testid="${id}-tree-archived"`);
    expect(html).not.toContain(`data-testid="${id}-tree-root"`);
    expect(html).not.toContain(`data-testid="${id}-tree-all"`);
    expect(html).toContain('Matériaux de construction');
  });
});
