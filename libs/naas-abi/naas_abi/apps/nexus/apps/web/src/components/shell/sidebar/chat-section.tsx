'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { MessageSquare, ChevronRight, Plus, Pin, Folder, MoreVertical, Archive, Edit2, Trash2, Star } from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { AgentAvatar } from '@/components/chat/agent-selector';
import { useFeature } from '@/hooks/use-feature';

const ConversationItem = React.memo(function ConversationItem({
  id,
  title,
  pinned,
  isActive,
  onClick,
  onPin,
  onArchive,
  onRename,
  onDelete,
  isRenaming,
  onStartRename,
  onCancelRename,
}: {
  id: string;
  title: string;
  pinned?: boolean;
  isActive: boolean;
  onClick: () => void;
  onPin: () => void;
  onArchive: () => void;
  onRename: (newTitle: string) => void;
  onDelete: () => void;
  isRenaming?: boolean;
  onStartRename: () => void;
  onCancelRename: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(title);

  const handleRenameSubmit = () => {
    if (editValue.trim() && editValue !== title) {
      onRename(editValue.trim());
    }
    onCancelRename();
  };

  if (isRenaming) {
    return (
      <div className="flex items-center gap-2 rounded-md px-2 py-1.5">
        <MessageSquare size={12} className="flex-shrink-0 text-muted-foreground" />
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleRenameSubmit();
            } else if (e.key === 'Escape') {
              onCancelRename();
            }
          }}
          onBlur={handleRenameSubmit}
          autoFocus
          className="flex-1 bg-transparent text-xs outline-none border-b border-workspace-accent"
        />
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={onClick}
        className={cn(
          'group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors',
          'hover:bg-workspace-accent-10',
          isActive && 'bg-workspace-accent-15 text-workspace-accent'
        )}
      >
        {pinned && <Pin size={12} className="flex-shrink-0 text-workspace-accent" />}
        <MessageSquare size={12} className="flex-shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate">{title}</span>
        <div
          className="flex-shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 cursor-pointer"
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
        >
          <MoreVertical size={12} />
        </div>
      </button>
      
      {/* Context Menu */}
      {showMenu && (
        <>
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setShowMenu(false)}
          />
          <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-md border border-border bg-popover p-1 shadow-lg">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPin();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Pin size={12} />
              {pinned ? 'Unpin' : 'Pin'}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onStartRename();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Edit2 size={12} />
              Rename
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onArchive();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Archive size={12} />
              Archive
            </button>
            <div className="my-1 h-px bg-border" />
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10"
            >
              <Trash2 size={12} />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
});

const ProjectGroup = React.memo(function ProjectGroup({
  name,
  conversations,
  activeId,
  onSelect,
  onPin,
  onArchive,
  onRename,
  onDelete,
  renamingId,
  onStartRename,
  onCancelRename,
}: {
  name: string;
  conversations: { id: string; title: string; pinned?: boolean }[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onPin: (id: string) => void;
  onArchive: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
  renamingId: string | null;
  onStartRename: (id: string) => void;
  onCancelRename: () => void;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="space-y-0.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronRight
          size={12}
          className={cn('transition-transform', expanded && 'rotate-90')}
        />
        <Folder size={12} />
        <span className="flex-1 truncate text-left">{name}</span>
        <span className="text-[10px]">{conversations.length}</span>
      </button>
      {expanded && (
        <div className="ml-3 space-y-0.5">
          {conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              id={conv.id}
              title={conv.title}
              pinned={conv.pinned}
              isActive={activeId === conv.id}
              onClick={() => onSelect(conv.id)}
              onPin={() => onPin(conv.id)}
              onArchive={() => onArchive(conv.id)}
              isRenaming={renamingId === conv.id}
              onStartRename={() => onStartRename(conv.id)}
              onRename={(newTitle) => onRename(conv.id, newTitle)}
              onCancelRename={onCancelRename}
              onDelete={() => onDelete(conv.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export function ChatSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [agentMenuId, setAgentMenuId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const {
    activeConversationId,
    setActiveConversation,
    projects,
    currentWorkspaceId,
    conversations: storeConversations,
    selectedAgent,
    agentExplicitlySelected,
    setSelectedAgent,
    clearAgentExplicitSelection,
    togglePinConversation,
    toggleArchiveConversation,
    renameConversation,
    deleteConversation,
  } = useWorkspaceStore();

  const { agents, setDefaultAgent } = useAgentsStore();
  // "agents" feature flag gates agent administration (edit, settings access).
  const canManageAgents = useFeature('agents');
  const safeAgents = useMemo(() => (Array.isArray(agents) ? agents : []), [agents]);

  // Derive from the reactive conversations state — calling the store's
  // getWorkspaceConversations() inside useMemo froze the list at first render
  // (the action reference never changes), so pin/rename/new-chat updates
  // never reached the sidebar.
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
  // New-chat state: on the chat route with no conversation open. The accent
  // highlight goes to "New Chat" unless the user explicitly picked an agent.
  const isNewChatState = isChatRoute && !activeConversationId;
  const isNewChatActive = isNewChatState && !agentExplicitlySelected;

  // Leaving the chat section drops any explicit agent selection, so coming
  // back always lands on the default new-chat state ("New Chat" highlighted).
  // Deliberately keyed on the route only: setting the flag while still on
  // another section (agent click → router.push('/chat')) must not clear it.
  useEffect(() => {
    if (!isChatRoute) clearAgentExplicitSelection();
  }, [isChatRoute, clearAgentExplicitSelection]);

  // Default agent first, then by most recently used (latest conversation
  // touched with that agent), never-used agents last in alphabetical order.
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
    const defaultAgent =
      safeAgents.find((a) => a.isDefault && a.enabled) ??
      safeAgents.find((a) => a.id === 'abi' && a.enabled) ??
      safeAgents.find((a) => a.enabled);
    if (defaultAgent) setSelectedAgent(defaultAgent.id);
    setActiveConversation(null);
    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
  }, [safeAgents, setSelectedAgent, setActiveConversation, router, currentWorkspaceId]);

  // Clicking the "Chat" section header resets to a blank new-chat state,
  // pre-selecting the workspace default agent (falling back to "abi" then first enabled).
  const handleChatHeaderNavigate = useCallback(() => {
    const defaultAgent =
      safeAgents.find((a) => a.isDefault && a.enabled) ??
      safeAgents.find((a) => a.id === 'abi' && a.enabled) ??
      safeAgents.find((a) => a.enabled);
    if (defaultAgent) setSelectedAgent(defaultAgent.id);
    setActiveConversation(null);
  }, [safeAgents, setSelectedAgent, setActiveConversation]);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversation(id);
    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
  }, [setActiveConversation, router, currentWorkspaceId]);

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
      {/* New Chat button */}
      <button
        type="button"
        onClick={handleNewChat}
        title="New chat (Ctrl+I)"
        className={cn(
          'flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium transition-colors',
          isNewChatActive
            ? 'bg-workspace-accent-15 text-workspace-accent'
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        <Plus size={12} />
        <span>New Chat</span>
      </button>

      {/* Agents */}
      <div className="space-y-0.5">
        {canManageAgents ? (
          <Link
            href={getWorkspacePath(currentWorkspaceId, '/settings/agents')}
            className="block px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            Agents
          </Link>
        ) : (
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Agents
          </p>
        )}
        {visibleAgents.map((agent) => {
          const isSelected = isNewChatState && agentExplicitlySelected && selectedAgent === agent.id;

          return (
            <div key={agent.id} className="relative">
              <button
                onClick={() => {
                  setSelectedAgent(agent.id, true);
                  setActiveConversation(null);
                  router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
                }}
                className={cn(
                  'group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors',
                  'hover:bg-workspace-accent-10',
                  isSelected && 'bg-workspace-accent-15 font-medium text-workspace-accent'
                )}
              >
                <span
                  className={cn(
                    'flex h-4 w-4 flex-shrink-0 items-center justify-center overflow-hidden rounded',
                    !agent.logoUrl && (isSelected ? 'text-workspace-accent' : 'text-muted-foreground')
                  )}
                >
                  <AgentAvatar agent={agent} size={12} />
                </span>
                <span className="flex-1 truncate">{agent.name}</span>
                {agent.isDefault && (
                  <span className="flex-shrink-0 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
                    Default
                  </span>
                )}
                <div
                  className="flex-shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 cursor-pointer"
                  onClick={(e) => {
                    e.stopPropagation();
                    setAgentMenuId(agentMenuId === agent.id ? null : agent.id);
                  }}
                >
                  <MoreVertical size={12} />
                </div>
              </button>

              {agentMenuId === agent.id && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setAgentMenuId(null)} />
                  <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-md border border-border bg-popover p-1 shadow-lg">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void setDefaultAgent(agent.id);
                        setAgentMenuId(null);
                      }}
                      disabled={agent.isDefault}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent disabled:cursor-default disabled:opacity-50 disabled:hover:bg-transparent"
                    >
                      <Star size={12} />
                      {agent.isDefault ? 'Default agent' : 'Set as default'}
                    </button>
                    {canManageAgents && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setAgentMenuId(null);
                          router.push(getWorkspacePath(currentWorkspaceId, `/settings/agents/${agent.id}`));
                        }}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
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
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronRight
              size={12}
              className={cn('flex-shrink-0 transition-transform', showAllAgents && 'rotate-90')}
            />
            <span>{showAllAgents ? 'Show less' : `Show ${hiddenAgentCount} more`}</span>
          </button>
        )}
      </div>

      {/* Pinned */}
      {pinnedConvs.length > 0 && (
        <div className="space-y-0.5">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Pinned
          </p>
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
              onStartRename={() => {
                setRenamingId(conv.id);
                setRenameValue(conv.title);
              }}
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
            />
          ))}
        </div>
      )}

      {/* Projects */}
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
          onStartRename={(id) => {
            const conv = conversations.find(c => c.id === id);
            if (conv) {
              setRenamingId(id);
              setRenameValue(conv.title);
            }
          }}
          onRename={(id, newTitle) => {
            renameConversation(id, newTitle);
            setRenamingId(null);
          }}
          onCancelRename={() => setRenamingId(null)}
          onDelete={(id) => {
            const conv = conversations.find(c => c.id === id);
            if (conv && confirm(`Delete "${conv.title}"?`)) {
              deleteConversation(id);
            }
          }}
        />
      ))}

      {/* Recent */}
      {recentConvs.length > 0 && (
        <div className="space-y-0.5">
          <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Recent
          </p>
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
              onStartRename={() => {
                setRenamingId(conv.id);
                setRenameValue(conv.title);
              }}
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
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {conversations.length === 0 && (
        <p className="px-2 py-2 text-xs text-muted-foreground">
          No conversations yet
        </p>
      )}
    </CollapsibleSection>
  );
}
