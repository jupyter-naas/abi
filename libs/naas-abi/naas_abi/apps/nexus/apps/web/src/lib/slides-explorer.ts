import type { SlidesProject } from '@/stores/slides';
import type { SlidesSeedTemplate } from '@/lib/slides-templates';

export type SlidesExplorerAction =
  | 'open-deck'
  | 'apply-template'
  | 'select-asset'
  | 'open-project'
  | 'noop';

export type SlidesExplorerIcon =
  | 'folder'
  | 'html'
  | 'image'
  | 'json'
  | 'md'
  | 'template'
  | 'presentation';

export type SlidesExplorerNode = {
  id: string;
  name: string;
  kind: 'folder' | 'file';
  icon: SlidesExplorerIcon;
  action: SlidesExplorerAction;
  children?: SlidesExplorerNode[];
  emptyLabel?: string;
  templateId?: string;
  slug?: string;
  hint?: string;
  accent?: string;
  renamable?: boolean;
};

export type SlidesTreeEntry = {
  name: string;
  path: string;
  type: string;
  size?: number;
};

export type SlidesProjectTree = {
  slug: string;
  root: string;
  entries: SlidesTreeEntry[];
  assets: SlidesTreeEntry[];
  embedded_images?: number;
  assets_note?: string | null;
};

const PROJECT_ROOT_FILES = new Set(['deck.html', 'project.json', 'readme.md']);
const NOISE_NAMES = new Set([
  '.gitkeep',
  '.git',
  '.coder',
  '.vscode',
  'node_modules',
  '.ds_store',
  'coder.yaml',
]);
const HASH_NAME_RE = /^[0-9a-f]{7,40}$/i;
const WS_HASH_RE = /^ws-[0-9a-f]{8,}$/i;

export const DEFAULT_EXPANDED_IDS = ['templates', 'assets'];

export function defaultExpandedIds(openSlug?: string | null): string[] {
  const ids = [...DEFAULT_EXPANDED_IDS];
  if (openSlug) {
    ids.unshift(`project:${openSlug}`);
    ids.push(`project:${openSlug}:assets`);
  }
  return ids;
}

export function entryBasename(name: string, path = ''): string {
  const raw = (name || path || '').replace(/\\/g, '/').replace(/\/+$/, '');
  const parts = raw.split('/').filter(Boolean);
  return parts[parts.length - 1] || '';
}

export function isUnderProjectRoot(path: string, root: string): boolean {
  const p = (path || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  const r = (root || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  if (!r || !p) return false;
  return p === r || p.startsWith(`${r}/`);
}

export function isNoiseName(name: string): boolean {
  const low = (name || '').toLowerCase();
  if (NOISE_NAMES.has(low)) return true;
  return HASH_NAME_RE.test(name) || WS_HASH_RE.test(name);
}

export function iconForName(name: string): SlidesExplorerIcon {
  const low = name.toLowerCase();
  if (low.endsWith('.html')) return 'html';
  if (low.endsWith('.json')) return 'json';
  if (low.endsWith('.md')) return 'md';
  if (/\.(svg|png|jpe?g|gif|webp|avif)$/i.test(low)) return 'image';
  return 'presentation';
}

function normalizeRoot(root: string): string {
  return root.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
}

/** Keep deck.html, project.json, README.md. Drop hashed InMemory dumps and Coder noise. */
export function curateProjectEntries(entries: SlidesTreeEntry[], root: string): SlidesTreeEntry[] {
  const rootN = normalizeRoot(root);
  const byName = new Map<string, SlidesTreeEntry>();
  for (const entry of entries) {
    const path = entry.path || entry.name;
    const name = entryBasename(entry.name, path);
    if (!name || isNoiseName(name)) continue;
    if (!isUnderProjectRoot(path, rootN) && !isUnderProjectRoot(entry.name, rootN)) {
      continue;
    }
    const key = name.toLowerCase();
    if (key === 'assets') {
      byName.set('assets', {
        name: 'assets',
        path: `${rootN}/assets`,
        type: 'dir',
      });
      continue;
    }
    if (!PROJECT_ROOT_FILES.has(key)) continue;
    byName.set(key, {
      name,
      path: `${rootN}/${name}`,
      type: 'file',
      size: entry.size,
    });
  }
  if (!byName.has('deck.html')) {
    byName.set('deck.html', { name: 'deck.html', path: `${rootN}/deck.html`, type: 'file' });
  }
  if (!byName.has('project.json')) {
    byName.set('project.json', {
      name: 'project.json',
      path: `${rootN}/project.json`,
      type: 'file',
    });
  }
  byName.set('assets', { name: 'assets', path: `${rootN}/assets`, type: 'dir' });
  return [...byName.values()].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

export function curateAssetEntries(entries: SlidesTreeEntry[], assetsDir: string): SlidesTreeEntry[] {
  const dir = normalizeRoot(assetsDir);
  const byName = new Map<string, SlidesTreeEntry>();
  for (const entry of entries) {
    const path = entry.path || entry.name;
    const name = entryBasename(entry.name, path);
    if (!name || isNoiseName(name)) continue;
    if (name.toLowerCase() === 'readme.md') continue;
    if (!isUnderProjectRoot(path, dir) && !isUnderProjectRoot(entry.name, dir)) {
      continue;
    }
    if (entry.type === 'dir') continue;
    byName.set(name, {
      name,
      path: `${dir}/${name}`,
      type: 'file',
      size: entry.size,
    });
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function projectFolderChildren(
  slug: string,
  tree: SlidesProjectTree | null | undefined,
  root: string,
): SlidesExplorerNode[] {
  const assetsDir = root ? `${root}/assets` : `slides/${slug}/assets`;
  const entries = curateProjectEntries(tree?.entries ?? [], root || `slides/${slug}`);
  const assets = curateAssetEntries(tree?.assets ?? [], assetsDir);
  const fileChildren: SlidesExplorerNode[] = [];
  for (const entry of entries) {
    if (entry.name === 'assets') continue;
    fileChildren.push({
      id: `project:${slug}:${entry.name}`,
      name: entry.name,
      kind: 'file',
      icon: iconForName(entry.name),
      action: entry.name === 'deck.html' ? 'open-deck' : 'noop',
      slug,
    });
  }
  fileChildren.push({
    id: `project:${slug}:assets`,
    name: 'assets',
    kind: 'folder',
    icon: 'folder',
    action: 'noop',
    emptyLabel: assets.length === 0 ? 'No images yet' : undefined,
    children: assets.map((asset) => ({
      id: `project:${slug}:asset:${asset.name}`,
      name: asset.name,
      kind: 'file' as const,
      icon: 'image' as const,
      action: 'select-asset' as const,
      slug,
    })),
  });
  return fileChildren;
}

export function buildSlidesExplorer(input: {
  projectTitle?: string | null;
  projectSlug?: string | null;
  projectRoot?: string | null;
  tree?: SlidesProjectTree | null;
  templates: SlidesSeedTemplate[];
  projects?: Pick<SlidesProject, 'slug' | 'title'>[];
  otherProjects?: Pick<SlidesProject, 'slug' | 'title'>[];
}): SlidesExplorerNode[] {
  const nodes: SlidesExplorerNode[] = [];
  const slug = input.projectSlug || input.tree?.slug || '';
  const root = normalizeRoot(
    input.projectRoot || input.tree?.root || (slug ? `slides/${slug}` : ''),
  );
  const listed = [
    ...(input.projects ?? []),
    ...(input.otherProjects ?? []),
  ].filter((row, index, all) => row.slug && all.findIndex((item) => item.slug === row.slug) === index);

  if (slug && !listed.some((row) => row.slug === slug)) {
    listed.unshift({ slug, title: input.projectTitle || slug });
  }

  for (const project of listed) {
    const isOpen = project.slug === slug;
    const title = isOpen
      ? input.projectTitle || project.title || project.slug
      : project.title || project.slug;
    nodes.push({
      id: `project:${project.slug}`,
      name: title,
      kind: 'folder',
      icon: 'folder',
      action: isOpen ? 'open-deck' : 'open-project',
      slug: project.slug,
      renamable: true,
      children: isOpen
        ? projectFolderChildren(project.slug, input.tree, root)
        : [
            {
              id: `project:${project.slug}:deck.html`,
              name: 'deck.html',
              kind: 'file',
              icon: 'html',
              action: 'open-project',
              slug: project.slug,
            },
            {
              id: `project:${project.slug}:assets`,
              name: 'assets',
              kind: 'folder',
              icon: 'folder',
              action: 'open-project',
              slug: project.slug,
              emptyLabel: 'Open to list files',
              children: [],
            },
          ],
    });
  }

  nodes.push({
    id: 'templates',
    name: 'Templates',
    kind: 'folder',
    icon: 'folder',
    action: 'noop',
    children: input.templates.map((template) => {
      const files =
        template.files?.length > 0 ? template.files : [{ name: 'deck.html', kind: 'html' }];
      return {
        id: `template:${template.id}`,
        name: template.name,
        kind: 'folder' as const,
        icon: 'template' as const,
        action: 'apply-template' as const,
        templateId: template.id,
        accent: template.preview_accent || template.preview_bg,
        children: [
          ...files.map((file) => ({
            id: `template:${template.id}:${file.name}`,
            name: file.name,
            kind: 'file' as const,
            icon: iconForName(file.name),
            action: 'apply-template' as const,
            templateId: template.id,
          })),
          {
            id: `template:${template.id}:assets`,
            name: 'assets',
            kind: 'folder' as const,
            icon: 'folder' as const,
            action: 'noop' as const,
            emptyLabel:
              (template.assets?.length ?? 0) === 0 ? 'None (embedded in deck.html)' : undefined,
            children: (template.assets ?? []).map((asset) => ({
              id: `template:${template.id}:asset:${asset.name}`,
              name: asset.name,
              kind: 'file' as const,
              icon: 'image' as const,
              action: 'select-asset' as const,
              templateId: template.id,
              hint: asset.kind === 'embedded' ? 'embedded' : undefined,
            })),
          },
        ],
      };
    }),
  });

  return nodes;
}
