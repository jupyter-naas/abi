'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { MessageSquare, ChevronRight, MoreVertical, Edit2, Star } from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { SidebarNewItem } from '@/components/shell/sidebar/sidebar-new-item';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { newChatPath, NEW_CHAT_SLUG } from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { AgentAvatar } from '@/components/chat/agent-selector';
import { useFeature } from '@/hooks/use-feature';
import { useStartNewChat } from '../lib/use-start-new-chat';
import { ConversationItem } from './conversation-item';
import { ProjectGroup } from './project-group';
import { chatRosterSections } from './chat-section-agents';
import './chat-components.css';

export function ChatSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const iconSize = isMobilePanel ? 14 : 12;
  const listItemProps = { mobilePanel: isMobilePanel };
  const router = useRouter();
  const pathname = usePathname();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [agentMenuId, setAgentMenuId] = useState<string | null>(null);

  const {
    activeConversationId,
    setActiveConversation,
    setMobilePendingChatSlug,
    projects,
    currentWorkspaceId,
    conversations: storeConversations,
    selectedAgent,
    agentExplicitlySelected,
    setSelectedAgent,
    togglePinConversation,
    toggleArchiveConversation,
    renameConversation,
    deleteConversation,
  } = useWorkspaceStore();

  const { agents, setDefaultAgent, fetchAgents } = useAgentsStore();
  const canManageAgents = useFeature('agents');
  const safeAgents = useMemo(() => (Array.isArray(agents) ? agents : []), [agents]);

  const allConversations = useMemo(
    () =>
      currentWorkspaceId
        ? storeConversations.filter((c) => c.workspaceId === currentWorkspaceId)
        : [],
    [storeConversations, currentWorkspaceId]
  );
  const safeProjects = useMemo(() => (Array.isArray(projects) ? projects : []), [projects]);
  const conversations = useMemo(() => allConversations.filter((c) => !c.archived), [allConversations]);
  const isChatRoute = pathname.startsWith(getWorkspacePath(currentWorkspaceId, '/chat'));
  const isNewChatState = isChatRoute && !activeConversationId;
  const isNewChatActive = isNewChatState && !agentExplicitlySelected;

  useEffect(() => {
    if (!currentWorkspaceId) return;
    void fetchAgents(currentWorkspaceId);
  }, [currentWorkspaceId, fetchAgents]);

  // Warm thread routes while the mobile list is visible so the first open feels instant.
  useEffect(() => {
    if (!isMobilePanel || !currentWorkspaceId) return;
    router.prefetch(newChatPath(currentWorkspaceId));
    for (const conv of conversations.slice(0, 15)) {
      router.prefetch(getWorkspacePath(currentWorkspaceId, `/chat/${conv.id}`));
    }
  }, [isMobilePanel, currentWorkspaceId, conversations, router]);

  const sortedAgents = useMemo(() => {
    const lastUsedAt = new Map<string, number>();
    for (const conv of allConversations) {
      if (!conv.agent) continue;
      const t = new Date(conv.updatedAt).getTime();
      if (t > (lastUsedAt.get(conv.agent) ?? 0)) lastUsedAt.set(conv.agent, t);
    }
    return safeAgents
      .filter((agent) => agent.enabled)
      .sort((a, b) => {
        if (a.isDefault !== b.isDefault) return a.isDefault ? -1 : 1;
        const usedDiff = (lastUsedAt.get(b.id) ?? 0) - (lastUsedAt.get(a.id) ?? 0);
        if (usedDiff !== 0) return usedDiff;
        return a.name.localeCompare(b.name);
      });
  }, [safeAgents, allConversations]);

  const { visible: visibleAgents, hiddenCount: hiddenAgentCount } = useMemo(
    () => chatRosterSections(sortedAgents, showAllAgents),
    [sortedAgents, showAllAgents]
  );

  const pinnedConvs = useMemo(() => conversations.filter((c) => c.pinned), [conversations]);
  const recentConvs = useMemo(() => conversations.filter((c) => !c.pinned && !c.projectId), [conversations]);

  const projectGroups = useMemo(() => {
    const projectConvs = conversations.filter((c) => c.projectId && !c.pinned);
    return safeProjects.map((project) => ({
      ...project,
      conversations: projectConvs.filter((c) => c.projectId === project.id),
    }));
  }, [conversations, safeProjects]);

  // Same action as the topnav File → New Chat.
  const handleNewChat = useStartNewChat();

  const handleChatHeaderNavigate = useCallback(() => {
    if (!agentExplicitlySelected) {
      const defaultAgent =
        safeAgents.find((a) => a.isDefault && a.enabled) ??
        safeAgents.find((a) => a.enabled);
      if (defaultAgent) setSelectedAgent(defaultAgent.id);
    }
    setActiveConversation(null);
  }, [safeAgents, agentExplicitlySelected, setSelectedAgent, setActiveConversation]);

  const handleSelectConversation = useCallback((id: string) => {
    setMobilePendingChatSlug(id);
    setActiveConversation(id);
    router.push(getWorkspacePath(currentWorkspaceId, `/chat/${id}`));
  }, [setMobilePendingChatSlug, setActiveConversation, router, currentWorkspaceId]);

  useEffect(() => {
    if (!currentWorkspaceId) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'i') return;
      if (e.altKey || e.shiftKey) return;
      e.preventDefault();
      handleNewChat();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentWorkspaceId, handleNewChat]);

  const labelClass = (asLink = false) =>
    `chat-section-label${isMobilePanel ? ' is-mobile-panel' : ''}${asLink ? ' is-link' : ''}`;

  const listRowClass = (active = false) =>
    `chat-list-row${active ? ' is-active' : ''}${isMobilePanel ? ' is-mobile-panel' : ''}`;

  return (
    <CollapsibleSection
      id="chat"
      icon={<MessageSquare size={18} />}
      label="Chat"
      description="Interact with ABI-powered agents"
      href={getWorkspacePath(currentWorkspaceId, '/chat')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={handleChatHeaderNavigate}
    >
      <SidebarNewItem
        label="New Chat"
        title="New chat (Ctrl+I)"
        onClick={handleNewChat}
        active={isNewChatActive}
        mobilePanel={isMobilePanel}
      />

      <div className="chat-section-group">
        {canManageAgents ? (
          <Link
            href={getWorkspacePath(currentWorkspaceId, '/settings/agents')}
            className={labelClass(true)}
          >
            Agents
          </Link>
        ) : (
          <p className={labelClass()}>Agents</p>
        )}
        {visibleAgents.length === 0 && (
          <p className="chat-section-hint">No agents available yet</p>
        )}
        {visibleAgents.map((agent) => {
          const isSelected = isNewChatState && agentExplicitlySelected && selectedAgent === agent.id;

          return (
            <div key={agent.id} className="chat-list-row-wrap">
              <button
                type="button"
                onClick={() => {
                  setSelectedAgent(agent.id, true);
                  setActiveConversation(null);
                  setMobilePendingChatSlug(NEW_CHAT_SLUG);
                  router.push(newChatPath(currentWorkspaceId));
                }}
                className={listRowClass(isSelected)}
              >
                <span
                  className={`chat-list-row-avatar${!agent.logoUrl ? (isSelected ? ' is-accent' : ' is-muted') : ''}`}
                >
                  <AgentAvatar agent={agent} size={iconSize} />
                </span>
                <span className="chat-list-row-title">{agent.name}</span>
                {agent.isDefault && (
                  <span className="chat-list-row-badge">Default</span>
                )}
                <div
                  className="chat-list-row-menu-trigger"
                  onClick={(e) => {
                    e.stopPropagation();
                    setAgentMenuId(agentMenuId === agent.id ? null : agent.id);
                  }}
                  role="presentation"
                >
                  <MoreVertical size={12} />
                </div>
              </button>

              {agentMenuId === agent.id && (
                <>
                  <div className="chat-context-menu-backdrop" onClick={() => setAgentMenuId(null)} />
                  <div className="chat-context-menu">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void setDefaultAgent(agent.id);
                        setAgentMenuId(null);
                      }}
                      disabled={agent.isDefault}
                      className="chat-context-menu-item"
                    >
                      <Star size={12} />
                      {agent.isDefault ? 'Default agent' : 'Set as default'}
                    </button>
                    {canManageAgents && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setAgentMenuId(null);
                          router.push(getWorkspacePath(currentWorkspaceId, `/settings/agents/${agent.id}`));
                        }}
                        className="chat-context-menu-item"
                      >
                        <Edit2 size={12} />
                        Edit agent
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          );
        })}
        {hiddenAgentCount > 0 && (
          <button
            type="button"
            onClick={() => setShowAllAgents(!showAllAgents)}
            className={`chat-section-show-more${isMobilePanel ? ' is-mobile-panel' : ''}`}
          >
            <ChevronRight
              size={iconSize}
              className={`chat-section-show-more-chevron${showAllAgents ? ' is-expanded' : ''}`}
            />
            <span>{showAllAgents ? 'Show less' : `Show ${hiddenAgentCount} more`}</span>
          </button>
        )}
      </div>

      {pinnedConvs.length > 0 && (
        <div className="chat-section-group">
          <p className={labelClass()}>Pinned</p>
          {pinnedConvs.map((conv) => (
            <ConversationItem
              key={conv.id}
              id={conv.id}
              title={conv.title}
              pinned
              isActive={isChatRoute && activeConversationId === conv.id}
              onClick={() => handleSelectConversation(conv.id)}
              onPin={() => togglePinConversation(conv.id)}
              onArchive={() => toggleArchiveConversation(conv.id)}
              isRenaming={renamingId === conv.id}
              onStartRename={() => setRenamingId(conv.id)}
              onRename={(newTitle) => {
                renameConversation(conv.id, newTitle);
                setRenamingId(null);
              }}
              onCancelRename={() => setRenamingId(null)}
              onDelete={() => {
                if (confirm(`Delete "${conv.title}"?`)) {
                  deleteConversation(conv.id);
                }
              }}
              {...listItemProps}
            />
          ))}
        </div>
      )}

      {projectGroups.filter((p) => p.conversations.length > 0).map((project) => (
        <ProjectGroup
          key={project.id}
          name={project.name}
          conversations={project.conversations}
          activeId={isChatRoute ? activeConversationId : null}
          onSelect={handleSelectConversation}
          onPin={togglePinConversation}
          onArchive={toggleArchiveConversation}
          renamingId={renamingId}
          onStartRename={(id) => setRenamingId(id)}
          onRename={(id, newTitle) => {
            renameConversation(id, newTitle);
            setRenamingId(null);
          }}
          onCancelRename={() => setRenamingId(null)}
          onDelete={(id) => {
            const conv = conversations.find((c) => c.id === id);
            if (conv && confirm(`Delete "${conv.title}"?`)) {
              deleteConversation(id);
            }
          }}
          {...listItemProps}
        />
      ))}

      {recentConvs.length > 0 && (
        <div className="chat-section-group">
          <p className={labelClass()}>Recent</p>
          {recentConvs.slice(0, 10).map((conv) => (
            <ConversationItem
              key={conv.id}
              id={conv.id}
              title={conv.title}
              isActive={isChatRoute && activeConversationId === conv.id}
              onClick={() => handleSelectConversation(conv.id)}
              onPin={() => togglePinConversation(conv.id)}
              onArchive={() => toggleArchiveConversation(conv.id)}
              isRenaming={renamingId === conv.id}
              onStartRename={() => setRenamingId(conv.id)}
              onRename={(newTitle) => {
                renameConversation(conv.id, newTitle);
                setRenamingId(null);
              }}
              onCancelRename={() => setRenamingId(null)}
              onDelete={() => {
                if (confirm(`Delete "${conv.title}"?`)) {
                  deleteConversation(conv.id);
                }
              }}
              {...listItemProps}
            />
          ))}
        </div>
      )}

      {conversations.length === 0 && (
        <p className="chat-section-empty">No conversations yet</p>
      )}
    </CollapsibleSection>
  );
}
