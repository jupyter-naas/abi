import { useWorkspaceStore, type Conversation } from './workspace';

/**
 * Which chat surface a subscription belongs to: the main thread or the
 * side-by-side compare pane. They track different conversations.
 */
export type ChatSurface = 'main' | 'pane';

/**
 * The slice of workspace state a chat thread needs to find its conversation.
 * Declared structurally so the selector can be unit-tested against a plain
 * object without standing up the whole store.
 */
export interface ChatThreadStateSlice {
  conversations: Conversation[];
  currentWorkspaceId: string | null;
  activeConversationId: string | null;
  paneConversationId: string | null;
}

/**
 * The conversation a chat surface renders, derived from state.
 *
 * IMPORTANT — this must stay a *state-derived* selector. It deliberately does
 * not call the `getWorkspaceConversations()` store action, even though that
 * action computes the same filter.
 *
 * zustand only re-renders a subscriber when its selector output stops being
 * `Object.is`-equal to the previous one. A selector that returns a store
 * *action* returns the same function reference forever, so it subscribes to
 * nothing: the component then derives its message list by calling that action
 * during render, and never repaints. That is exactly how the chat thread froze
 * mid-stream — tool-call steps and tokens piled up in the store while the
 * screen showed a stale turn until an unrelated state change or a page refresh
 * forced a repaint.
 *
 * Reading `state.conversations` here keeps the subscription live:
 * `updateLastMessage` rebuilds the conversation object on every stream chunk,
 * so the output identity changes and the thread repaints. It also stays narrow
 * — writes to other conversations or unrelated UI state leave the output
 * identical, so there is no re-render storm.
 *
 * Covered by chat-thread-selectors.test.ts.
 */
export function selectSurfaceConversation(
  state: ChatThreadStateSlice,
  surface: ChatSurface
): Conversation | undefined {
  const { currentWorkspaceId } = state;
  if (!currentWorkspaceId) return undefined;

  const conversationId = surface === 'pane' ? state.paneConversationId : state.activeConversationId;
  if (!conversationId) return undefined;

  return state.conversations.find(
    (c) => c.id === conversationId && c.workspaceId === currentWorkspaceId
  );
}

/**
 * Reactive subscription to the conversation a chat surface renders.
 * Re-renders the caller on every store write that changes that conversation —
 * i.e. once per streamed chunk — and on nothing else.
 */
export function useSurfaceConversation(surface: ChatSurface): Conversation | undefined {
  return useWorkspaceStore((s) => selectSurfaceConversation(s, surface));
}
