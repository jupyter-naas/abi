import { useMemo } from 'react';

import { useWorkspaceStore, type Conversation } from './workspace';

/** A conversation as the sidebar lists it: everything except its messages. */
export type ConversationSummary = Omit<Conversation, 'messages'>;

export interface ConversationListStateSlice {
  conversations: Conversation[];
  currentWorkspaceId: string | null;
}

const SUMMARY_KEYS = [
  'id',
  'workspaceId',
  'title',
  'agent',
  'createdAt',
  'updatedAt',
  'pinned',
  'archived',
  'projectId',
  'isDraft',
  'slidesSlug',
  'documentsSlug',
  'sheetsSlug',
] as const satisfies readonly (keyof ConversationSummary)[];

const sameValue = (a: unknown, b: unknown): boolean => {
  if (Object.is(a, b)) return true;
  // Persisted conversations can carry dates as strings; compare instants.
  if ((a instanceof Date || typeof a === 'string') && (b instanceof Date || typeof b === 'string')) {
    const ta = new Date(a).getTime();
    const tb = new Date(b).getTime();
    return !Number.isNaN(ta) && ta === tb;
  }
  return false;
};

const sameSummary = (summary: ConversationSummary, conv: Conversation): boolean =>
  SUMMARY_KEYS.every((key) => sameValue(summary[key], conv[key]));

const toSummary = (conv: Conversation): ConversationSummary => {
  const { messages: _messages, ...summary } = conv;
  return summary;
};

/**
 * Memoizing selector for the current workspace's conversation list.
 *
 * Streaming rebuilds the active conversation object on every chunk (its
 * `messages` change). The sidebar only reads metadata, so this keeps each
 * summary, and the array, referentially stable until a listed field changes;
 * zustand then skips re-rendering subscribers during streaming.
 *
 * Stateful: create one per subscriber (see `useWorkspaceConversationSummaries`).
 */
export function createConversationSummariesSelector() {
  let cache = new Map<string, ConversationSummary>();
  let last: ConversationSummary[] = [];

  return (state: ConversationListStateSlice): ConversationSummary[] => {
    const workspaceId = state.currentWorkspaceId;
    const next: ConversationSummary[] = [];
    const nextCache = new Map<string, ConversationSummary>();
    if (workspaceId) {
      for (const conv of state.conversations) {
        if (conv.workspaceId !== workspaceId) continue;
        const previous = cache.get(conv.id);
        const summary = previous && sameSummary(previous, conv) ? previous : toSummary(conv);
        nextCache.set(conv.id, summary);
        next.push(summary);
      }
    }
    cache = nextCache;
    if (next.length === last.length && next.every((summary, i) => summary === last[i])) {
      return last;
    }
    last = next;
    return next;
  };
}

/** The current workspace's conversations, without messages; stable while only content streams. */
export function useWorkspaceConversationSummaries(): ConversationSummary[] {
  const selector = useMemo(() => createConversationSummariesSelector(), []);
  return useWorkspaceStore(selector);
}
