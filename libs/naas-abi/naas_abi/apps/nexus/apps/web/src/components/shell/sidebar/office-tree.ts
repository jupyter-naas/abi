/**
 * Tree model for the Documents, Sheets and Slides sidebars.
 *
 * The sidebar is a plain file explorer: one root folder holding every item in the
 * workspace, each item expanding to the files that really exist for it on disk
 * (document.html / workbook.html / deck.html, project.json, assets/). The shape comes
 * from two server calls, `GET /projects` for the items and `GET /projects/{slug}/tree`
 * for one item's files, so this module keeps the mapping and the ordering rules in
 * one pure place the view can render without knowing about fetching.
 */

import { officeItemHref, type OfficeKind } from '@/components/office/office-kinds';

export type OfficeTreeEntryType = 'file' | 'dir';

export type OfficeTreeEntry = {
  name: string;
  path: string;
  type: OfficeTreeEntryType;
};

/** Shape of `GET /api/{documents|sheets|slides}/projects/{slug}/tree`. */
export type OfficeProjectTree = {
  slug: string;
  root: string;
  entries: OfficeTreeEntry[];
  assets: OfficeTreeEntry[];
};

export type OfficeTreeFileNode = {
  name: string;
  path: string;
  type: OfficeTreeEntryType;
  /** True for the file the pane is actually editing. */
  open: boolean;
  children: OfficeTreeFileNode[];
};

export type OfficeTreeItemNode = {
  slug: string;
  label: string;
  href: string;
  /** True for the item the route is on; the view renders this as selection. */
  active: boolean;
  /** Empty until the item's tree has been fetched. */
  files: OfficeTreeFileNode[];
  filesLoaded: boolean;
};

/** The fields of a project the tree reads. */
export type OfficeTreeProject = { slug: string; title: string };

/** True on `/workspace/{id}/{kind}` with no item slug. */
export function isOfficeGalleryPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path === galleryHref || path === `${galleryHref}/`;
}

/** True on an item (or `/{kind}/new`), not the gallery. */
export function isOfficeNestedPath(pathname: string | undefined, galleryHref: string): boolean {
  if (!pathname) return false;
  const path = pathname.split('?')[0] ?? '';
  return path.startsWith(`${galleryHref}/`);
}

export function officeTreeItemLabel(project: OfficeTreeProject): string {
  return (project.title || '').trim() || project.slug;
}

/** Folders before files, then case-insensitive by name, like a file explorer. */
function compareEntries(a: OfficeTreeEntry, b: OfficeTreeEntry): number {
  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
}

/**
 * One item's files, with the fetched assets nested under the `assets` folder.
 *
 * Two things get dropped, both of them scaffolding rather than content:
 *
 *   - `.gitkeep` and the seed README, the way the server already leaves them
 *     out of its own assets listing;
 *   - an empty `assets` folder, which the server appends to every item whether
 *     or not one was ever committed. A folder the user did add stays, even
 *     empty, because only `assets` is synthesised.
 */
export function officeTreeFileNodes(
  tree: OfficeProjectTree | null | undefined,
  opts: { fileName: string; open?: boolean },
): OfficeTreeFileNode[] {
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
      open: Boolean(opts.open) && entry.name === opts.fileName,
      children: entry.name === 'assets' && entry.type === 'dir' ? assets : [],
    }));
}

/**
 * Keep the open item in the explorer even when GET /projects omitted it
 * (list race, Forgejo down, or a silent fetch miss).
 */
function withOpenProject(
  projects: OfficeTreeProject[],
  openSlug?: string | null,
  openTitle?: string | null,
): OfficeTreeProject[] {
  const listed = projects.filter((project) => Boolean(project?.slug));
  if (!openSlug || listed.some((project) => project.slug === openSlug)) {
    return listed;
  }
  return [...listed, { slug: openSlug, title: (openTitle || '').trim() || openSlug }];
}

export function buildOfficeTree(
  kind: Pick<OfficeKind, 'id' | 'fileName'>,
  projects: OfficeTreeProject[],
  opts: {
    workspaceId: string;
    openSlug?: string | null;
    openTitle?: string | null;
    /** Fetched per item; an item with no entry here renders unexpanded. */
    trees?: Record<string, OfficeProjectTree | undefined>;
  },
): OfficeTreeItemNode[] {
  const trees = opts.trees ?? {};
  return withOpenProject(projects, opts.openSlug, opts.openTitle)
    .map((project) => {
      const active = Boolean(opts.openSlug) && project.slug === opts.openSlug;
      const tree = trees[project.slug];
      return {
        slug: project.slug,
        label: officeTreeItemLabel(project),
        href: officeItemHref(kind, opts.workspaceId, project.slug),
        active,
        files: officeTreeFileNodes(tree, { fileName: kind.fileName, open: active }),
        filesLoaded: Boolean(tree),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Items that should start expanded.
 *
 * Only the open item, so the tree opens on what the user is editing without
 * unfolding every item in the workspace.
 */
export function initialExpandedItems(openSlug: string | null | undefined): string[] {
  return openSlug ? [openSlug] : [];
}
