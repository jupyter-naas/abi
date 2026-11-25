import { DOCUMENTS_KIND } from '@/components/office/office-kinds';
import {
  officeTreeFileNodes,
  type OfficeProjectTree as DocumentsProjectTree,
  type OfficeTreeFileNode as SectionsTreeFileNode,
} from '@/components/shell/sidebar/office-tree';

export type SectionsComposerFile = {
  name: string;
  path: string;
  open: boolean;
};

/** Flatten a document tree to files only. Directories are not counted. */
export function flattenSectionsComposerFiles(nodes: SectionsTreeFileNode[]): SectionsComposerFile[] {
  const files: SectionsComposerFile[] = [];
  const walk = (node: SectionsTreeFileNode) => {
    if (node.type === 'file') {
      files.push({ name: node.name, path: node.path, open: node.open });
    }
    for (const child of node.children) walk(child);
  };
  for (const node of nodes) walk(node);
  return files;
}

/** The open document path we already know about, before GET /tree returns. */
export function sectionsComposerFallbackFiles(
  path: string | null | undefined,
): SectionsComposerFile[] {
  if (!path) return [];
  const name = path.split('/').filter(Boolean).pop() || path;
  return [{ name, path, open: true }];
}

/**
 * Files for the composer Files tab.
 *
 * Until the tree is fetched, show the open document.html. After a fetch, use the
 * real list (which may be empty). Never invent project.json or a review list.
 */
export function sectionsComposerFiles(
  tree: DocumentsProjectTree | null | undefined,
  fallbackPath?: string | null,
): SectionsComposerFile[] {
  if (!tree) return sectionsComposerFallbackFiles(fallbackPath);
  return flattenSectionsComposerFiles(officeTreeFileNodes(tree, { fileName: DOCUMENTS_KIND.fileName, open: true }));
}
