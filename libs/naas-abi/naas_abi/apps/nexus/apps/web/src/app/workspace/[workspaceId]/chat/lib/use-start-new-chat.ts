'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAgentsStore } from '@/stores/agents';
import { useWorkspaceStore } from '@/stores/workspace';
import { newChatPath, NEW_CHAT_SLUG } from './chat-route';

/**
 * Start a new chat: fall back to the default agent unless one was picked on
 * purpose, clear the open conversation and go to the new-chat route. Shared by
 * the sidebar's New Chat button (and Ctrl+I) and the topnav File → New Chat,
 * so both behave the same.
 */
export function useStartNewChat(): () => void {
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const agentExplicitlySelected = useWorkspaceStore((s) => s.agentExplicitlySelected);
  const setSelectedAgent = useWorkspaceStore((s) => s.setSelectedAgent);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const setMobilePendingChatSlug = useWorkspaceStore((s) => s.setMobilePendingChatSlug);
  const agents = useAgentsStore((s) => s.agents);

  return useCallback(() => {
    if (!agentExplicitlySelected) {
      const safeAgents = Array.isArray(agents) ? agents : [];
      const defaultAgent =
        safeAgents.find((a) => a.isDefault && a.enabled) ??
        safeAgents.find((a) => a.enabled);
      if (defaultAgent) setSelectedAgent(defaultAgent.id);
    }
    setActiveConversation(null);
    setMobilePendingChatSlug(NEW_CHAT_SLUG);
    router.push(newChatPath(currentWorkspaceId));
  }, [agents, agentExplicitlySelected, setSelectedAgent, setActiveConversation, setMobilePendingChatSlug, router, currentWorkspaceId]);
}
