import type { Conversation } from '@/stores/workspace';

/** Persist key for the slug-to-pane-thread map. */
export function slidesPaneConversationKey(workspaceId: string, slug: string): string {
  return `${workspaceId}::${slug}`;
}

export function slidesDeckConversationPath(slug: string): string {
  return `slides/${slug}/deck.html`;
}

const GENERIC_TITLES = new Set(['untitled presentation', 'new conversation', 'new chat']);

function normalizeTitle(value: string): string {
  return value.trim().toLowerCase();
}

function isGenericTitle(value: string): boolean {
  return GENERIC_TITLES.has(normalizeTitle(value));
}

/** True when a thread is clearly about this deck (tag, path, or title). */
export function conversationMatchesSlidesSlug(
  conversation: Pick<Conversation, 'title' | 'slidesSlug'> & {
    messages?: Array<{ content?: string }>;
  },
  slug: string,
  deckTitle?: string | null,
): boolean {
  const trimmed = slug.trim();
  if (!trimmed) return false;
  if (conversation.slidesSlug === trimmed) return true;
  const needle = `slides/${trimmed}`;
  if (conversation.title.includes(needle)) return true;
  if ((conversation.messages ?? []).some((message) => (message.content || '').includes(needle))) {
    return true;
  }
  if (deckTitle && !isGenericTitle(conversation.title) && !isGenericTitle(deckTitle)) {
    const title = normalizeTitle(conversation.title);
    const deck = normalizeTitle(deckTitle);
    if (title === deck || title.startsWith(`${deck} `) || deck.startsWith(`${title} `)) {
      return true;
    }
  }
  return false;
}

export function findSlidesPaneConversationId(opts: {
  workspaceId: string;
  slug: string;
  conversations: Conversation[];
  boundId?: string | null;
  deckTitle?: string | null;
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
    .filter((conversation) => conversationMatchesSlidesSlug(conversation, slug, opts.deckTitle))
    .sort(
      (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
    );
  return ranked[0]?.id ?? null;
}

export function dropSlidesPaneConversationKeys(
  map: Record<string, string>,
  conversationId: string,
): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(map)) {
    if (value !== conversationId) next[key] = value;
  }
  return next;
}
