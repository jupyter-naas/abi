/**
 * The chat URL is the single source of truth for which chat view is showing.
 *
 *   /workspace/{id}/chat        → conversation list (mobile) / launcher (desktop)
 *   /workspace/{id}/chat/new    → blank thread, default agent preselected
 *   /workspace/{id}/chat/{cid}  → existing thread
 */

export const NEW_CHAT_SLUG = 'new';

export interface ChatRoute {
  /** On a chat route at all. */
  isChatRoute: boolean;
  /** Existing conversation id, or null for the list and for a blank new chat. */
  conversationId: string | null;
  /** A thread is open: either an existing conversation or a blank new one. */
  isThread: boolean;
}

// Lookahead, not a consumed terminator: consuming it lets the engine backtrack
// into "no slug" on /chat/{id}?query and silently report the list instead.
const CHAT_SEGMENT = /(?:^|\/)chat(?:\/([^/?#]+))?(?=[/?#]|$)/;

export function parseChatRoute(pathname: string | null | undefined): ChatRoute {
  const match = pathname ? CHAT_SEGMENT.exec(pathname) : null;
  if (!match) {
    return { isChatRoute: false, conversationId: null, isThread: false };
  }
  const slug = match[1] ?? null;
  return {
    isChatRoute: true,
    conversationId: slug && slug !== NEW_CHAT_SLUG ? slug : null,
    isThread: slug !== null,
  };
}

/** Path of the blank-new-chat thread for a workspace. */
export function newChatPath(workspaceId: string | null): string {
  return workspaceId ? `/workspace/${workspaceId}/chat/${NEW_CHAT_SLUG}` : `/chat/${NEW_CHAT_SLUG}`;
}

/**
 * True when the mobile shell should show a chat thread (URL or in-flight tap).
 * Uses an ephemeral pending slug so the list can dismiss before router.push
 * updates the pathname. Never rely on persisted activeConversationId here —
 * that would reopen the last thread on a cold start at /chat.
 */
export function isMobileChatThreadOpen(
  route: ChatRoute,
  pendingSlug: string | null,
): boolean {
  return route.isThread || (route.isChatRoute && pendingSlug !== null);
}

/** Conversation id for ChatInterface on mobile, from URL or pending navigation. */
export function resolveMobileThreadConversationId(
  route: ChatRoute,
  pendingSlug: string | null,
): string | null {
  if (route.conversationId) return route.conversationId;
  if (pendingSlug && pendingSlug !== NEW_CHAT_SLUG) return pendingSlug;
  return null;
}

/**
 * Where the chat URL should point, so every conversation has a shareable link.
 * Returns null when the URL is already right and must be left alone.
 */
export function nextChatUrl(
  pathname: string | null | undefined,
  workspaceId: string | null,
  activeConversationId: string | null
): string | null {
  if (!pathname || !workspaceId) return null;

  const base = `/workspace/${workspaceId}/chat`;
  // Mid-workspace-switch: a pending navigation to another workspace would race
  // with this rewrite and get reverted.
  if (!pathname.startsWith(base)) return null;

  // /chat/new is a real destination (blank thread), not a stale URL to clean up.
  // Collapsing it to /chat would send the mobile shell back to the conversation list.
  if (!activeConversationId && pathname === `${base}/${NEW_CHAT_SLUG}`) return null;

  const target = activeConversationId ? `${base}/${activeConversationId}` : base;
  return pathname === target ? null : target;
}
