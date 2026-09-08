import {
  slidesTreeFileNodes,
  type SlidesProjectTree,
  type SlidesTreeFileNode,
} from '@/components/shell/sidebar/slides-tree';
import type { SlidesRuntimeStatus } from '@/stores/slides';

export type SlidesComposerFile = {
  name: string;
  path: string;
  open: boolean;
};

/** Flatten a deck tree to files only. Directories are not counted. */
export function flattenSlidesComposerFiles(nodes: SlidesTreeFileNode[]): SlidesComposerFile[] {
  const files: SlidesComposerFile[] = [];
  const walk = (node: SlidesTreeFileNode) => {
    if (node.type === 'file') {
      files.push({ name: node.name, path: node.path, open: node.open });
    }
    for (const child of node.children) walk(child);
  };
  for (const node of nodes) walk(node);
  return files;
}

/** The open deck path we already know about, before GET /tree returns. */
export function slidesComposerFallbackFiles(
  path: string | null | undefined,
): SlidesComposerFile[] {
  if (!path) return [];
  const name = path.split('/').filter(Boolean).pop() || path;
  return [{ name, path, open: true }];
}

/**
 * Files for the composer Files tab.
 *
 * Until the tree is fetched, show the open deck.html. After a fetch, use the
 * real list (which may be empty). Never invent project.json or a review list.
 */
export function slidesComposerFiles(
  tree: SlidesProjectTree | null | undefined,
  fallbackPath?: string | null,
): SlidesComposerFile[] {
  if (!tree) return slidesComposerFallbackFiles(fallbackPath);
  return flattenSlidesComposerFiles(slidesTreeFileNodes(tree, { deckOpen: true }));
}

export function slidesComposerRuntimeSuffix(
  runtime?: SlidesRuntimeStatus | null,
): string {
  if (runtime === 'error' || runtime === 'degraded') return 'Forgejo fallback';
  if (runtime === 'ready') return 'workspace';
  return '';
}
