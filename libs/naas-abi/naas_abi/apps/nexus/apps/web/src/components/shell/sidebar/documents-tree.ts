/**
 * Tree model for the Documents sidebar.
 *
 * The sidebar is a plain file explorer: one root folder holding every document in
 * the workspace, each document expanding to the files that really exist for it on
 * disk (document.html, project.json, assets/). The shape comes from two server
 * calls, `GET /projects` for the documents and `GET /projects/{slug}/tree` for one
 * document's files, so this module keeps the mapping and the ordering rules in one
 * pure place the view can render without knowing about fetching.
 */

import type { DocumentsProject } from '@/stores/documents';

export type SectionsTreeEntryType = 'file' | 'dir';

export type SectionsTreeEntry = {
  name: string;
  path: string;
  type: SectionsTreeEntryType;
};

/** Shape of `GET /api/documents/projects/{slug}/tree`. */
export type DocumentsProjectTree = {
  slug: string;
  root: string;
  entries: SectionsTreeEntry[];
  assets: SectionsTreeEntry[];
};

export type SectionsTreeFileNode = {
  name: string;
  path: string;
  type: SectionsTreeEntryType;
  /** True for the file the document pane is actually editing. */
  open: boolean;
  children: SectionsTreeFileNode[];
};

export type SectionsTreeDocumentNode = {
  slug: string;
  label: string;
  href: string;
  /** True for the document the route is on; the view renders this as selection. */
  active: boolean;
  /** Empty until the document's tree has been fetched. */
  files: SectionsTreeFileNode[];
  filesLoaded: boolean;
};

/**
 * Root label.
 *
 * The documents live under `documents/<workspace>/<slug>` in the workspace repo, so
 * `sections` is the one folder that genuinely contains all of them. Naming the
 * root after the real directory keeps the tree honest instead of inventing a
 * marketing label.
 */
export const SLIDES_TREE_ROOT_LABEL = 'documents';

/** First sidebar row: cover gallery, same idea as Apps' "All apps". */
export const SLIDES_ALL_ROW_LABEL = 'All sections';

/** The file a document opens in the Documents pane. */
export const SLIDES_DECK_FILE_NAME = 'document.html';

/** True on `/workspace/{id}/documents` with no document slug. */
export function isSectionsGalleryPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path === galleryHref || path === `${galleryHref}/`;
}

/** True on a document (or `/documents/new`), not the gallery. */
export function isDocumentsNestedPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path.startsWith(`${galleryHref}/`);
}

export function sectionsTreeDocumentLabel(project: Pick<DocumentsProject, 'slug' | 'title'>): string {
  return (project.title || '').trim() || project.slug;
}

export function sectionsTreeDocumentHref(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(slug)}`;
}

/** Folders before files, then case-insensitive by name, like a file explorer. */
function compareEntries(a: SectionsTreeEntry, b: SectionsTreeEntry): number {
  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
}

/**
 * One document's files, with the fetched assets nested under the `assets` folder.
 *
 * Two things get dropped, both of them scaffolding rather than document content:
 *
 *   - `.gitkeep` and the seed README, the way the server already leaves them
 *     out of its own assets listing;
 *   - an empty `assets` folder, which the server appends to every document whether
 *     or not one was ever committed. A folder the user did add stays, even
 *     empty, because only `assets` is synthesised.
 */
export function sectionsTreeFileNodes(
  tree: DocumentsProjectTree | null | undefined,
  opts: { documentOpen?: boolean } = {},
): SectionsTreeFileNode[] {
  if (!tree) return [];
  const hidden = new Set(['.gitkeep', 'README.md']);

  const assets = [...(tree.assets ?? [])]
    .filter((entry) => entry.name && !hidden.has(entry.name))
    .sort(compareEntries)
    .map((entry) => ({
      name: entry.name,
      path: entry.path,
      type: entry.type,
      open: false,
      children: [],
    }));

  return [...(tree.entries ?? [])]
    .filter((entry) => entry.name && !hidden.has(entry.name))
    .filter((entry) => entry.name !== 'assets' || assets.length > 0)
    .sort(compareEntries)
    .map((entry) => ({
      name: entry.name,
      path: entry.path,
      type: entry.type,
      open: Boolean(opts.documentOpen) && entry.name === SLIDES_DECK_FILE_NAME,
      children: entry.name === 'assets' && entry.type === 'dir' ? assets : [],
    }));
}

/**
 * Keep the open document in the explorer even when GET /projects omitted it
 * (list race, Forgejo down, or a silent fetch miss).
 */
function withOpenProject(
  projects: DocumentsProject[],
  openSlug?: string | null,
  openTitle?: string | null,
): DocumentsProject[] {
  const listed = projects.filter((project) => Boolean(project?.slug));
  if (!openSlug || listed.some((project) => project.slug === openSlug)) {
    return listed;
  }
  return [
    ...listed,
    {
      slug: openSlug,
      title: (openTitle || '').trim() || openSlug,
      branch: `documents/${openSlug}`,
      document_path: `documents/${openSlug}/document.html`,
      template_id: '',
    },
  ];
}

export function buildSectionsTree(
  projects: DocumentsProject[],
  opts: {
    workspaceId: string;
    openSlug?: string | null;
    openTitle?: string | null;
    /** Fetched per document; a document with no entry here renders unexpanded. */
    trees?: Record<string, DocumentsProjectTree | undefined>;
  },
): SectionsTreeDocumentNode[] {
  const trees = opts.trees ?? {};
  return withOpenProject(projects, opts.openSlug, opts.openTitle)
    .map((project) => {
      const active = Boolean(opts.openSlug) && project.slug === opts.openSlug;
      const tree = trees[project.slug];
      return {
        slug: project.slug,
        label: sectionsTreeDocumentLabel(project),
        href: sectionsTreeDocumentHref(opts.workspaceId, project.slug),
        active,
        files: sectionsTreeFileNodes(tree, { documentOpen: active }),
        filesLoaded: Boolean(tree),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Documents that should start expanded.
 *
 * Only the open document, so the tree opens on what the user is editing without
 * unfolding every document in the workspace.
 */
export function initialExpandedDocuments(openSlug: string | null | undefined): string[] {
  return openSlug ? [openSlug] : [];
}
