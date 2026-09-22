/**
 * Tree model for the Sheets sidebar.
 *
 * The sidebar is a plain file explorer: one root folder holding every workbook
 * in the workspace, each workbook expanding to the files that really exist for
 * it on disk (workbook.html, project.json, assets/). The shape comes from two
 * server calls, `GET /projects` for the workbooks and `GET /projects/{slug}/tree`
 * for one workbook's files, so this module keeps the mapping and the ordering
 * rules in one pure place the view can render without knowing about fetching.
 */

import type { SheetsProject } from '@/stores/sheets';

export type SheetsTreeEntryType = 'file' | 'dir';

export type SheetsTreeEntry = {
  name: string;
  path: string;
  type: SheetsTreeEntryType;
};

/** Shape of `GET /api/sheets/projects/{slug}/tree`. */
export type SheetsProjectTree = {
  slug: string;
  root: string;
  entries: SheetsTreeEntry[];
  assets: SheetsTreeEntry[];
};

export type SheetsTreeFileNode = {
  name: string;
  path: string;
  type: SheetsTreeEntryType;
  /** True for the file the workbook pane is actually editing. */
  open: boolean;
  children: SheetsTreeFileNode[];
};

export type SheetsTreeWorkbookNode = {
  slug: string;
  label: string;
  href: string;
  /** True for the workbook the route is on; the view renders this as selection. */
  active: boolean;
  /** Empty until the workbook's tree has been fetched. */
  files: SheetsTreeFileNode[];
  filesLoaded: boolean;
};

/**
 * Root label.
 *
 * The workbooks live under `sheets/<workspace>/<slug>` in the workspace repo, so
 * `sheets` is the one folder that genuinely contains all of them. Naming the
 * root after the real directory keeps the tree honest instead of inventing a
 * marketing label.
 */
export const SHEETS_TREE_ROOT_LABEL = 'sheets';

/** First sidebar row: cover gallery, same idea as Apps' "All apps". */
export const SHEETS_ALL_ROW_LABEL = 'All sheets';

/** The file a workbook opens in the Sheets pane. */
export const SHEETS_WORKBOOK_FILE_NAME = 'workbook.html';

/** True on `/workspace/{id}/sheets` with no workbook slug. */
export function isSheetsGalleryPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path === galleryHref || path === `${galleryHref}/`;
}

/** True on a workbook (or `/sheets/new`), not the gallery. */
export function isSheetsNestedPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path.startsWith(`${galleryHref}/`);
}

export function sheetsTreeWorkbookLabel(project: Pick<SheetsProject, 'slug' | 'title'>): string {
  return (project.title || '').trim() || project.slug;
}

export function sheetsTreeWorkbookHref(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/sheets/${encodeURIComponent(slug)}`;
}

/** Folders before files, then case-insensitive by name, like a file explorer. */
function compareEntries(a: SheetsTreeEntry, b: SheetsTreeEntry): number {
  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
}

/**
 * One workbook's files, with the fetched assets nested under the `assets` folder.
 *
 * Two things get dropped, both of them scaffolding rather than workbook content:
 *
 *   - `.gitkeep` and the seed README, the way the server already leaves them
 *     out of its own assets listing;
 *   - an empty `assets` folder, which the server appends to every workbook whether
 *     or not one was ever committed. A folder the user did add stays, even
 *     empty, because only `assets` is synthesised.
 */
export function sheetsTreeFileNodes(
  tree: SheetsProjectTree | null | undefined,
  opts: { workbookOpen?: boolean } = {},
): SheetsTreeFileNode[] {
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
      open: Boolean(opts.workbookOpen) && entry.name === SHEETS_WORKBOOK_FILE_NAME,
      children: entry.name === 'assets' && entry.type === 'dir' ? assets : [],
    }));
}

/**
 * Keep the open workbook in the explorer even when GET /projects omitted it
 * (list race, Forgejo down, or a silent fetch miss).
 */
function withOpenProject(
  projects: SheetsProject[],
  openSlug?: string | null,
  openTitle?: string | null,
): SheetsProject[] {
  const listed = projects.filter((project) => Boolean(project?.slug));
  if (!openSlug || listed.some((project) => project.slug === openSlug)) {
    return listed;
  }
  return [
    ...listed,
    {
      slug: openSlug,
      title: (openTitle || '').trim() || openSlug,
      branch: `sheets/${openSlug}`,
      workbook_path: `sheets/${openSlug}/workbook.html`,
      template_id: '',
    },
  ];
}

export function buildSheetsTree(
  projects: SheetsProject[],
  opts: {
    workspaceId: string;
    openSlug?: string | null;
    openTitle?: string | null;
    /** Fetched per workbook; a workbook with no entry here renders unexpanded. */
    trees?: Record<string, SheetsProjectTree | undefined>;
  },
): SheetsTreeWorkbookNode[] {
  const trees = opts.trees ?? {};
  return withOpenProject(projects, opts.openSlug, opts.openTitle)
    .map((project) => {
      const active = Boolean(opts.openSlug) && project.slug === opts.openSlug;
      const tree = trees[project.slug];
      return {
        slug: project.slug,
        label: sheetsTreeWorkbookLabel(project),
        href: sheetsTreeWorkbookHref(opts.workspaceId, project.slug),
        active,
        files: sheetsTreeFileNodes(tree, { workbookOpen: active }),
        filesLoaded: Boolean(tree),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Workbooks that should start expanded.
 *
 * Only the open workbook, so the tree opens on what the user is editing without
 * unfolding every workbook in the workspace.
 */
export function initialExpandedSheetsWorkbooks(openSlug: string | null | undefined): string[] {
  return openSlug ? [openSlug] : [];
}
