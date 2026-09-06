/**
 * Tree model for the Slides sidebar.
 *
 * The sidebar is a plain file explorer: one root folder holding every deck in
 * the workspace, each deck expanding to the files that really exist for it on
 * disk (deck.html, project.json, assets/). The shape comes from two server
 * calls, `GET /projects` for the decks and `GET /projects/{slug}/tree` for one
 * deck's files, so this module keeps the mapping and the ordering rules in one
 * pure place the view can render without knowing about fetching.
 */

import type { SlidesProject } from '@/stores/slides';

export type SlidesTreeEntryType = 'file' | 'dir';

export type SlidesTreeEntry = {
  name: string;
  path: string;
  type: SlidesTreeEntryType;
};

/** Shape of `GET /api/slides/projects/{slug}/tree`. */
export type SlidesProjectTree = {
  slug: string;
  root: string;
  entries: SlidesTreeEntry[];
  assets: SlidesTreeEntry[];
};

export type SlidesTreeFileNode = {
  name: string;
  path: string;
  type: SlidesTreeEntryType;
  /** True for the file the deck pane is actually editing. */
  open: boolean;
  children: SlidesTreeFileNode[];
};

export type SlidesTreeDeckNode = {
  slug: string;
  label: string;
  href: string;
  /** True for the deck the route is on; the view renders this as selection. */
  active: boolean;
  /** Empty until the deck's tree has been fetched. */
  files: SlidesTreeFileNode[];
  filesLoaded: boolean;
};

/**
 * Root label.
 *
 * The decks live under `slides/<workspace>/<slug>` in the workspace repo, so
 * `slides` is the one folder that genuinely contains all of them. Naming the
 * root after the real directory keeps the tree honest instead of inventing a
 * marketing label.
 */
export const SLIDES_TREE_ROOT_LABEL = 'slides';

/** The file a deck opens in the Slides pane. */
export const SLIDES_DECK_FILE_NAME = 'deck.html';

export function slidesTreeDeckLabel(project: Pick<SlidesProject, 'slug' | 'title'>): string {
  return (project.title || '').trim() || project.slug;
}

export function slidesTreeDeckHref(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/slides/${encodeURIComponent(slug)}`;
}

/** Folders before files, then case-insensitive by name, like a file explorer. */
function compareEntries(a: SlidesTreeEntry, b: SlidesTreeEntry): number {
  if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
}

function trimPath(path: string): string {
  return (path || '').replace(/\/+$/, '');
}

/**
 * One deck's files, with the fetched assets nested under the `assets` folder.
 *
 * Three things get dropped, all of them scaffolding rather than deck content:
 *
 *   - `.gitkeep` and the seed README, the way the server already leaves them
 *     out of its own assets listing;
 *   - the deck folder itself, which the source control adapter can return as
 *     its own child because `git ls-tree <ref> <dir>` without a trailing slash
 *     reports the directory entry instead of what is inside it;
 *   - an empty `assets` folder, which the server appends to every deck whether
 *     or not one was ever committed. A folder the user did add stays, even
 *     empty, because only `assets` is synthesised.
 */
export function slidesTreeFileNodes(
  tree: SlidesProjectTree | null | undefined,
  opts: { deckOpen?: boolean } = {},
): SlidesTreeFileNode[] {
  if (!tree) return [];
  const hidden = new Set(['.gitkeep', 'README.md']);
  const root = trimPath(tree.root);
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
    .filter((entry) => !root || trimPath(entry.path) !== root)
    .filter((entry) => entry.name !== 'assets' || assets.length > 0)
    .sort(compareEntries)
    .map((entry) => ({
      name: entry.name,
      path: entry.path,
      type: entry.type,
      open: Boolean(opts.deckOpen) && entry.name === SLIDES_DECK_FILE_NAME,
      children: entry.name === 'assets' && entry.type === 'dir' ? assets : [],
    }));
}

/**
 * Decks as tree nodes, sorted by their display name.
 *
 * Abi renames a deck from the brief on its first write, so the label has to
 * come from the server project list rather than the slug.
 */
export function buildSlidesTree(
  projects: SlidesProject[],
  opts: {
    workspaceId: string;
    openSlug?: string | null;
    /** Fetched per deck; a deck with no entry here renders unexpanded. */
    trees?: Record<string, SlidesProjectTree | undefined>;
  },
): SlidesTreeDeckNode[] {
  const trees = opts.trees ?? {};
  return [...projects]
    .filter((project) => Boolean(project?.slug))
    .map((project) => {
      const active = Boolean(opts.openSlug) && project.slug === opts.openSlug;
      const tree = trees[project.slug];
      return {
        slug: project.slug,
        label: slidesTreeDeckLabel(project),
        href: slidesTreeDeckHref(opts.workspaceId, project.slug),
        active,
        files: slidesTreeFileNodes(tree, { deckOpen: active }),
        filesLoaded: Boolean(tree),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
}

/**
 * Decks that should start expanded.
 *
 * Only the open deck, so the tree opens on what the user is editing without
 * unfolding every deck in the workspace.
 */
export function initialExpandedSlidesDecks(openSlug: string | null | undefined): string[] {
  return openSlug ? [openSlug] : [];
}
