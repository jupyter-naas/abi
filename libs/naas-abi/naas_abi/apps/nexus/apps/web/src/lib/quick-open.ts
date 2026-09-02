export const QUICK_OPEN_GROUPS = ['navigate', 'workspace', 'app', 'chat', 'file'] as const;

export type QuickOpenGroup = (typeof QUICK_OPEN_GROUPS)[number];

export type QuickOpenAction =
  | { kind: 'href'; href: string; panel?: string | null }
  | { kind: 'workspace'; workspaceId: string }
  | { kind: 'file'; source: string; path: string; type: 'file' | 'folder' };

export type QuickOpenItem = {
  id: string;
  group: QuickOpenGroup;
  label: string;
  hint?: string;
  action: QuickOpenAction;
};

export type QuickOpenSection = {
  id: string;
  label: string;
  href: string;
  feature?: string;
};

/** Surfaces the palette can jump to. Hrefs are workspace-relative. */
export const QUICK_OPEN_SECTIONS: readonly QuickOpenSection[] = [
  { id: 'home', label: 'Home', href: '/home' },
  { id: 'apps', label: 'Apps', href: '/apps', feature: 'apps' },
  { id: 'lab', label: 'Lab', href: '/lab', feature: 'agents' },
  { id: 'files', label: 'Files', href: '/files', feature: 'files' },
  { id: 'chat', label: 'Chat', href: '/chat', feature: 'chat' },
  { id: 'search', label: 'Search', href: '/search', feature: 'search' },
  { id: 'maps', label: 'Maps', href: '/maps/presence', feature: 'maps' },
  { id: 'ontology', label: 'Ontology', href: '/ontology', feature: 'ontology' },
  { id: 'graph', label: 'Knowledge Graph', href: '/graph/network', feature: 'graph' },
  { id: 'datasets', label: 'Datasets', href: '/datasets', feature: 'datasets' },
  { id: 'slides', label: 'Slides', href: '/slides', feature: 'slides' },
  { id: 'code', label: 'Code', href: '/code/workspaces', feature: 'code' },
  { id: 'marketplace', label: 'Marketplace', href: '/marketplace', feature: 'marketplace' },
  { id: 'settings', label: 'Settings', href: '/settings', feature: 'settings.workspace' },
];

export const QUICK_OPEN_GROUP_LABEL: Record<QuickOpenGroup, string> = {
  navigate: 'Navigate',
  workspace: 'Workspaces',
  app: 'Apps',
  chat: 'Chats',
  file: 'Files',
};

/** Persist rehydrate often stores Date fields as ISO strings. Never call .getTime() on them. */
export function conversationUpdatedAtMs(
  value: Date | string | number | null | undefined,
): number {
  if (value == null || value === '') return 0;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? ms : 0;
}

export function scoreQuickOpen(item: QuickOpenItem, query: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const label = item.label.toLowerCase();
  const hint = (item.hint || '').toLowerCase();
  if (label === q) return 3;
  if (label.startsWith(q)) return 2;
  if (label.includes(q) || hint.includes(q)) return 1;
  return 0;
}

export function filterQuickOpenItems(
  items: readonly QuickOpenItem[],
  query: string,
): QuickOpenItem[] {
  const q = query.trim().toLowerCase();
  const matched = q ? items.filter((item) => scoreQuickOpen(item, q) > 0) : [...items];
  if (!q) return matched;
  return matched.sort((a, b) => {
    const group =
      QUICK_OPEN_GROUPS.indexOf(a.group) - QUICK_OPEN_GROUPS.indexOf(b.group);
    if (group) return group;
    const score = scoreQuickOpen(b, q) - scoreQuickOpen(a, q);
    if (score) return score;
    return a.label.localeCompare(b.label);
  });
}

export function groupQuickOpenItems(
  items: readonly QuickOpenItem[],
): { group: QuickOpenGroup; items: QuickOpenItem[] }[] {
  const buckets = new Map<QuickOpenGroup, QuickOpenItem[]>();
  for (const group of QUICK_OPEN_GROUPS) buckets.set(group, []);
  for (const item of items) {
    buckets.get(item.group)?.push(item);
  }
  return QUICK_OPEN_GROUPS
    .map((group) => ({ group, items: buckets.get(group) ?? [] }))
    .filter((entry) => entry.items.length > 0);
}

export function buildQuickOpenItems(input: {
  workspaceId: string;
  workspaces: { id: string; name: string }[];
  sections: { id: string; label: string; href: string }[];
  apps: { id: string; name: string }[];
  chats: { id: string; title: string }[];
  files: { source: string; path: string; name: string; type: 'file' | 'folder' }[];
}): QuickOpenItem[] {
  const items: QuickOpenItem[] = [];

  for (const section of input.sections) {
    items.push({
      id: `nav:${section.id}`,
      group: 'navigate',
      label: section.label,
      action: { kind: 'href', href: section.href, panel: section.id === 'home' ? null : section.id },
    });
  }

  for (const workspace of input.workspaces) {
    items.push({
      id: `ws:${workspace.id}`,
      group: 'workspace',
      label: workspace.name,
      hint: workspace.id === input.workspaceId ? 'Current' : undefined,
      action: { kind: 'workspace', workspaceId: workspace.id },
    });
  }

  for (const app of input.apps) {
    items.push({
      id: `app:${app.id}`,
      group: 'app',
      label: app.name,
      action: {
        kind: 'href',
        href: `/workspace/${input.workspaceId}/apps?open=${encodeURIComponent(app.id)}`,
        panel: 'apps',
      },
    });
  }

  for (const chat of input.chats) {
    items.push({
      id: `chat:${chat.id}`,
      group: 'chat',
      label: chat.title || 'Untitled chat',
      action: {
        kind: 'href',
        href: `/workspace/${input.workspaceId}/chat/${chat.id}`,
        panel: 'chat',
      },
    });
  }

  for (const file of input.files) {
    items.push({
      id: `file:${file.source}:${file.path}`,
      group: 'file',
      label: file.name,
      hint: file.path,
      action: {
        kind: 'file',
        source: file.source,
        path: file.path,
        type: file.type,
      },
    });
  }

  return items;
}
