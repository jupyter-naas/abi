/**
 * The Documents sidebar tree is a file explorer, so this pins the parts a
 * redesign keeps breaking:
 *
 *   - no section banners, only folders and files;
 *   - documents are anchors into the app, so cmd-click and middle-click work and
 *     a plain click keeps the workspace shell and the chat pane;
 *   - the document being edited is shown by selection, not by a header;
 *   - documents carry the name Abi generated from the topic.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

vi.mock('next/link', () => ({
  default: ({ children, ...props }: Record<string, unknown> & { children?: unknown }) =>
    createElement('a', props, children as never),
}));

import { SectionsTreeView } from './documents-tree-view';
import { buildSectionsTree, type DocumentsProjectTree } from './documents-tree';
import type { DocumentsProject } from '@/stores/documents';

function project(slug: string, title: string): DocumentsProject {
  return {
    slug,
    title,
    branch: 'main',
    document_path: `documents/ws/${slug}/document.html`,
    template_id: 'minimal-light-v1',
  };
}

const documentTree: DocumentsProjectTree = {
  slug: 'materiaux',
  root: 'documents/ws/materiaux',
  entries: [
    { name: 'document.html', path: 'documents/ws/materiaux/document.html', type: 'file' },
    { name: 'project.json', path: 'documents/ws/materiaux/project.json', type: 'file' },
    { name: 'assets', path: 'documents/ws/materiaux/assets', type: 'dir' },
  ],
  assets: [{ name: 'logo.png', path: 'documents/ws/materiaux/assets/logo.png', type: 'file' }],
};

const documents = buildSectionsTree(
  [project('materiaux', 'Matériaux de construction'), project('ai-news', 'Latest Ai News 2')],
  { workspaceId: 'ws-1', openSlug: 'materiaux', trees: { materiaux: documentTree } },
);

function markup(props: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(
    createElement(SectionsTreeView, {
      documents,
      rootHref: '/workspace/ws-1/documents',
      currentPath: '/workspace/ws-1/documents/materiaux',
      rootExpanded: true,
      onToggleRoot: () => {},
      expandedDocuments: ['materiaux'],
      onToggleDocument: () => {},
      expandedDirs: [],
      onToggleDir: () => {},
      onOpenDocument: () => {},
      ...props,
    } as never),
  );
}

describe('SectionsTreeView', () => {
  it('has no editorial section headers', () => {
    const html = markup();
    for (const banner of ['OPEN PRESENTATION', 'Open document', 'TEMPLATES', 'Templates', 'All projects']) {
      expect(html).not.toContain(banner);
    }
  });

  it('shows one root folder holding the documents', () => {
    const html = markup();
    expect(html).toContain('>sections</span>');
    expect((html.match(/data-testid="documents-tree-root"/g) ?? []).length).toBe(1);
  });

  it('lists documents by the name Abi generated', () => {
    const html = markup();
    expect(html).toContain('Matériaux de construction');
    expect(html).toContain('Latest Ai News 2');
  });

  it('links documents into the app instead of a new window', () => {
    const html = markup();
    expect(html).toContain('href="/workspace/ws-1/documents/materiaux"');
    expect(html).toContain('href="/workspace/ws-1/documents/ai-news"');
    expect(html).not.toContain('target=');
    expect(html).not.toContain('_blank');
  });

  it('keeps documents as anchors so cmd-click and middle-click still work', () => {
    const html = markup();
    expect(html).toMatch(/<a[^>]*data-testid="documents-tree-document"/);
  });

  it('marks the open document as the current page', () => {
    const html = markup();
    expect(html).toMatch(/data-slug="materiaux"[^>]*aria-current="page"|aria-current="page"[^>]*data-slug="materiaux"/);
    expect((html.match(/aria-current="page"/g) ?? []).length).toBe(1);
  });

  it('does not claim a document is the current page from the sections index', () => {
    const html = markup({ currentPath: '/workspace/ws-1/documents' });
    const documents = html.match(/<a[^>]*data-testid="documents-tree-document"[^>]*>/g) ?? [];
    expect(documents.some((row) => row.includes('aria-current'))).toBe(false);
    // The last document opened still reads as selected, the way an editor keeps
    // showing which file you were in.
    expect(html).toContain('bg-workspace-accent-15');
  });

  it('puts All sections first and marks it current on the gallery', () => {
    const html = markup({ currentPath: '/workspace/ws-1/documents' });
    expect(html).toContain('>All sections</span>');
    expect(html.indexOf('documents-tree-all')).toBeLessThan(html.indexOf('documents-tree-root'));
    expect(html).toMatch(
      /data-testid="documents-tree-all"[^>]*aria-current="page"|aria-current="page"[^>]*data-testid="documents-tree-all"/,
    );
    expect(html).toContain('href="/workspace/ws-1/documents"');
  });

  it('does not highlight All sections on an open document', () => {
    const html = markup();
    const all = html.match(/<a[^>]*data-testid="documents-tree-all"[^>]*>/g) ?? [];
    expect(all.length).toBe(1);
    expect(all[0]).not.toContain('aria-current');
  });

  it('shows selection on the open document and not on the others', () => {
    const html = markup();
    const rows = html.match(/<a[^>]*data-testid="documents-tree-document"[^>]*>/g) ?? [];
    const selected = rows.filter((row) => row.includes('bg-workspace-accent-15'));
    expect(rows.length).toBe(2);
    expect(selected.length).toBe(1);
    expect(selected[0]).toContain('data-slug="materiaux"');
  });

  it('expands the open document to the files that exist on disk', () => {
    const html = markup();
    expect(html).toContain('document.html');
    expect(html).toContain('project.json');
    expect(html).toContain('>assets</span>');
  });

  it('leaves a collapsed document unexpanded', () => {
    const html = markup({ expandedDocuments: [] });
    expect(html).not.toContain('project.json');
  });

  it('hides the whole tree when the root is collapsed', () => {
    const html = markup({ rootExpanded: false });
    expect(html).not.toContain('Matériaux de construction');
    expect(html).toContain('>sections</span>');
  });

  it('gives every folder a real disclosure button', () => {
    const html = markup();
    expect(html).toContain('aria-label="Collapse sections"');
    expect(html).toContain('aria-label="Collapse Matériaux de construction"');
    expect(html).toContain('aria-label="Expand Latest Ai News 2"');
    expect(html).toContain('aria-label="Expand assets"');
  });

  it('nests a fetched asset under the assets folder once opened', () => {
    expect(markup()).not.toContain('logo.png');
    expect(markup({ expandedDirs: ['documents/ws/materiaux/assets'] })).toContain('logo.png');
  });

  it('routes document.html to its document', () => {
    const html = markup();
    expect(html).toMatch(/<a[^>]*href="\/workspace\/ws-1\/documents\/materiaux"[^>]*data-testid="documents-tree-file"/);
  });

  it('says so when the workspace has no document yet', () => {
    expect(markup({ documents: [] })).toContain('No documents yet');
  });

  it('puts Rename and Archive on a document row when the chat actions are wired', () => {
    const html = markup({
      onStartRename: () => {},
      onRename: () => {},
      onCancelRename: () => {},
      onArchive: () => {},
    });
    expect(html).toContain('data-testid="documents-project-menu"');
  });

  it('lists archived documents without a second sections root', () => {
    const html = markup({ hideRoot: true, emptyLabel: 'No archived documents' });
    expect(html).toContain('data-testid="documents-tree-archived"');
    expect(html).not.toContain('data-testid="documents-tree-root"');
    expect(html).not.toContain('data-testid="documents-tree-all"');
    expect(html).toContain('Matériaux de construction');
  });
});
