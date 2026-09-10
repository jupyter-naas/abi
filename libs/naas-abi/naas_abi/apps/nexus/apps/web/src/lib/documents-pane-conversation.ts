import type { Conversation } from '@/stores/workspace';

/** Persist key for the slug-to-pane-thread map. */
export function documentsPaneConversationKey(workspaceId: string, slug: string): string {
  return `${workspaceId}::${slug}`;
}

export function documentConversationPath(slug: string): string {
  return `documents/${slug}/document.html`;
}

/** Namespaced Forgejo/sidecar path. Legacy unscoped path is only a fallback. */
export function openDocumentPath(workspaceId: string, slug: string): string {
  const ws = workspaceId.trim();
  const clean = slug.trim();
  if (ws && clean) return `documents/${ws}/${clean}/document.html`;
  if (clean) return `documents/${clean}/document.html`;
  return '';
}

export function openDocumentBranch(workspaceId: string, slug: string): string {
  const ws = workspaceId.trim();
  const clean = slug.trim();
  if (ws && clean) return `documents/${ws}/${clean}`;
  if (clean) return `documents/${clean}`;
  return '';
}

const GENERIC_TITLES = new Set(['untitled document', 'new conversation', 'new chat']);

function normalizeTitle(value: string): string {
  return value.trim().toLowerCase();
}

function isGenericTitle(value: string): boolean {
  return GENERIC_TITLES.has(normalizeTitle(value));
}

/** True when a thread is clearly about this document (tag, path, or title). */
export function conversationMatchesDocumentSlug(
  conversation: Pick<Conversation, 'title' | 'documentsSlug'> & {
    messages?: Array<{ content?: string }>;
  },
  slug: string,
  documentTitle?: string | null,
): boolean {
  const trimmed = slug.trim();
  if (!trimmed) return false;
  if (conversation.documentsSlug === trimmed) return true;
  const needle = `documents/${trimmed}`;
  if (conversation.title.includes(needle)) return true;
  if ((conversation.messages ?? []).some((message) => (message.content || '').includes(needle))) {
    return true;
  }
  if (documentTitle && !isGenericTitle(conversation.title) && !isGenericTitle(documentTitle)) {
    const title = normalizeTitle(conversation.title);
    const document = normalizeTitle(documentTitle);
    if (title === document || title.startsWith(`${document} `) || document.startsWith(`${title} `)) {
      return true;
    }
  }
  return false;
}

export function findDocumentsPaneConversationId(opts: {
  workspaceId: string;
  slug: string;
  conversations: Conversation[];
  boundId?: string | null;
  documentTitle?: string | null;
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
    .filter((conversation) => conversationMatchesDocumentSlug(conversation, slug, opts.documentTitle))
    .sort(
      (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
    );
  return ranked[0]?.id ?? null;
}

export function dropDocumentsPaneConversationKeys(
  map: Record<string, string>,
  conversationId: string,
): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(map)) {
    if (value !== conversationId) next[key] = value;
  }
  return next;
}
