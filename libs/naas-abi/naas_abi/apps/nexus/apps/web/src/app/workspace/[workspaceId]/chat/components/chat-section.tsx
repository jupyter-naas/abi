'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { MessageSquare, ChevronRight, Plus, MoreVertical, Edit2, Trash2, Star, Zap } from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useSkillsStore } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { newChatPath, NEW_CHAT_SLUG } from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { AgentAvatar } from '@/components/chat/agent-selector';
import { useFeature } from '@/hooks/use-feature';
import { ConversationItem } from './conversation-item';
import { ProjectGroup } from './project-group';
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
  const [showAllSkills, setShowAllSkills] = useState(false);
  const [skillMenuId, setSkillMenuId] = useState<string | null>(null);

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
  const canUseSkills = useFeature('skills');
  const { skillsByWorkspace, deleteSkill } = useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const setPendingComposerText = useWorkspaceStore((s) => s.setPendingComposerText);
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
    void fetchAgents(currentWorkspaceId, true);
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

  const AGENTS_PREVIEW_COUNT = 5;
  const visibleAgents = showAllAgents ? sortedAgents : sortedAgents.slice(0, AGENTS_PREVIEW_COUNT);
  const hiddenAgentCount = sortedAgents.length - AGENTS_PREVIEW_COUNT;

  const sortedSkills = useMemo(() => {
    const workspaceSkills = currentWorkspaceId
      ? (skillsByWorkspace[currentWorkspaceId] ?? [])
      : [];
    return workspaceSkills
      .filter((s) => s.enabled)
      .sort((a, b) => {
        const ta = a.lastUsedAt ? new Date(a.lastUsedAt).getTime() : 0;
        const tb = b.lastUsedAt ? new Date(b.lastUsedAt).getTime() : 0;
        if (ta !== tb) return tb - ta;
        return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
      });
  }, [skillsByWorkspace, currentWorkspaceId]);

  const SKILLS_PREVIEW_COUNT = 3;
  const visibleSkills = showAllSkills ? sortedSkills : sortedSkills.slice(0, SKILLS_PREVIEW_COUNT);
  const hiddenSkillCount = sortedSkills.length - SKILLS_PREVIEW_COUNT;

  const handleUseSkill = useCallback(
    (slug: string) => {
      setPendingComposerText(`/${slug} `);
      setMobilePendingChatSlug(NEW_CHAT_SLUG);
      router.push(newChatPath(currentWorkspaceId));
    },
    [setPendingComposerText, setMobilePendingChatSlug, router, currentWorkspaceId]
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

  const handleNewChat = useCallback(() => {
    if (!agentExplicitlySelected) {
      const defaultAgent =
        safeAgents.find((a) => a.isDefault && a.enabled) ??
        safeAgents.find((a) => a.enabled);
      if (defaultAgent) setSelectedAgent(defaultAgent.id);
    }
    setActiveConversation(null);
    setMobilePendingChatSlug(NEW_CHAT_SLUG);
    router.push(newChatPath(currentWorkspaceId));
  }, [safeAgents, agentExplicitlySelected, setSelectedAgent, setActiveConversation, setMobilePendingChatSlug, router, currentWorkspaceId]);

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
      <button
        type="button"
        onClick={handleNewChat}
        title="New chat (Ctrl+I)"
        className={`chat-section-new-chat${isNewChatActive ? ' is-active' : ''}${isMobilePanel ? ' is-mobile-panel' : ''}`}
      >
        <Plus size={iconSize} />
        <span>New Chat</span>
      </button>

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

      {canUseSkills && (
        <div className="chat-section-group">
          <Link
            href={getWorkspacePath(currentWorkspaceId, '/settings/skills')}
            className={labelClass(true)}
          >
            Skills
          </Link>
          {sortedSkills.length === 0 && (
            <p className="chat-section-hint">Type /create-skill in the chat to add one</p>
          )}
          {visibleSkills.map((skill) => (
            <div key={skill.id} className="chat-list-row-wrap">
              <button
                type="button"
                onClick={() => handleUseSkill(skill.slug)}
                title={skill.description || skill.name}
                className={listRowClass()}
              >
                <Zap size={iconSize} className="chat-list-row-icon" />
                <span className="chat-list-row-title">
                  {skill.name}
                  <span className="chat-list-row-skill-slug">/{skill.slug}</span>
                </span>
                <div
                  className="chat-list-row-menu-trigger"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSkillMenuId(skillMenuId === skill.id ? null : skill.id);
                  }}
                  role="presentation"
                >
                  <MoreVertical size={12} />
                </div>
              </button>

              {skillMenuId === skill.id && (
                <>
                  <div className="chat-context-menu-backdrop" onClick={() => setSkillMenuId(null)} />
                  <div className="chat-context-menu">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSkillMenuId(null);
                        router.push(getWorkspacePath(currentWorkspaceId, `/settings/skills/${skill.id}`));
                      }}
                      className="chat-context-menu-item"
                    >
                      <Edit2 size={12} />
                      Edit skill
                    </button>
                    {(skill.scope !== 'user' || skill.userId === currentUserId) && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSkillMenuId(null);
                          if (confirm(`Delete skill "/${skill.slug}"?`)) {
                            void deleteSkill(skill.id).catch((err) =>
                              alert(err instanceof Error ? err.message : 'Failed to delete skill')
                            );
                          }
                        }}
                        className="chat-context-menu-item is-destructive"
                      >
                        <Trash2 size={12} />
                        Delete
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
          {hiddenSkillCount > 0 && (
            <button
              type="button"
              onClick={() => setShowAllSkills(!showAllSkills)}
              className={`chat-section-show-more${isMobilePanel ? ' is-mobile-panel' : ''}`}
            >
              <ChevronRight
                size={iconSize}
                className={`chat-section-show-more-chevron${showAllSkills ? ' is-expanded' : ''}`}
              />
              <span>{showAllSkills ? 'Show less' : `Show ${hiddenSkillCount} more`}</span>
            </button>
          )}
        </div>
      )}

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
