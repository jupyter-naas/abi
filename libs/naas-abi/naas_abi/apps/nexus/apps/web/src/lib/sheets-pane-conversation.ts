import type { Conversation } from '@/stores/workspace';

/** Persist key for the slug-to-pane-thread map. */
export function sheetsPaneConversationKey(workspaceId: string, slug: string): string {
  return `${workspaceId}::${slug}`;
}

export function sheetsWorkbookConversationPath(slug: string): string {
  return `sheets/${slug}/workbook.html`;
}

/** Namespaced Forgejo/sidecar path. Legacy unscoped path is only a fallback. */
export function sheetsOpenWorkbookPath(workspaceId: string, slug: string): string {
  const ws = workspaceId.trim();
  const clean = slug.trim();
  if (ws && clean) return `sheets/${ws}/${clean}/workbook.html`;
  if (clean) return `sheets/${clean}/workbook.html`;
  return '';
}

export function sheetsOpenWorkbookBranch(workspaceId: string, slug: string): string {
  const ws = workspaceId.trim();
  const clean = slug.trim();
  if (ws && clean) return `sheets/${ws}/${clean}`;
  if (clean) return `sheets/${clean}`;
  return '';
}

const GENERIC_TITLES = new Set(['untitled workbook', 'new conversation', 'new chat']);

function normalizeTitle(value: string): string {
  return value.trim().toLowerCase();
}

function isGenericTitle(value: string): boolean {
  return GENERIC_TITLES.has(normalizeTitle(value));
}

/** True when a thread is clearly about this workbook (tag, path, or title). */
export function conversationMatchesSheetsSlug(
  conversation: Pick<Conversation, 'title' | 'sheetsSlug'> & {
    messages?: Array<{ content?: string }>;
  },
  slug: string,
  workbookTitle?: string | null,
): boolean {
  const trimmed = slug.trim();
  if (!trimmed) return false;
  if (conversation.sheetsSlug === trimmed) return true;
  const needle = `sheets/${trimmed}`;
  if (conversation.title.includes(needle)) return true;
  if ((conversation.messages ?? []).some((message) => (message.content || '').includes(needle))) {
    return true;
  }
  if (workbookTitle && !isGenericTitle(conversation.title) && !isGenericTitle(workbookTitle)) {
    const title = normalizeTitle(conversation.title);
    const workbook = normalizeTitle(workbookTitle);
    if (title === workbook || title.startsWith(`${workbook} `) || workbook.startsWith(`${title} `)) {
      return true;
    }
  }
  return false;
}

export function findSheetsPaneConversationId(opts: {
  workspaceId: string;
  slug: string;
  conversations: Conversation[];
  boundId?: string | null;
  workbookTitle?: string | null;
}): string | null {
  const slug = opts.slug.trim();
  const workspaceId = opts.workspaceId.trim();
  if (!slug || !workspaceId) return null;
  const inWorkspace = opts.conversations.filter(
    (conversation) => conversation.workspaceId === workspaceId && !conversation.archived,
  );
  if (opts.boundId && inWorkspace.some((conversation) => conversation.id === opts.boundId)) {
    return opts.boundId;
  }
  const ranked = inWorkspace
    .filter((conversation) => conversationMatchesSheetsSlug(conversation, slug, opts.workbookTitle))
    .sort(
      (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
    );
  return ranked[0]?.id ?? null;
}

export function dropSheetsPaneConversationKeys(
  map: Record<string, string>,
  conversationId: string,
): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(map)) {
    if (value !== conversationId) next[key] = value;
  }
  return next;
}
