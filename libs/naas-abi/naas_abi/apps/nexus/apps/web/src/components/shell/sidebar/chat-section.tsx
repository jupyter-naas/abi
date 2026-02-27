'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { MessageSquare, ChevronRight, Plus, Pin, Folder, MoreVertical, Bot, Settings, Archive, Edit2, Trash2 } from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath, agentIconComponents } from './utils';

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

export function ChatSection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [agentsExpanded, setAgentsExpanded] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const {
    activeConversationId,
    setActiveConversation,
    createConversation,
    projects,
    currentWorkspaceId,
    getWorkspaceConversations,
    selectedAgent,
    setSelectedAgent,
    togglePinConversation,
    toggleArchiveConversation,
    renameConversation,
    deleteConversation,
  } = useWorkspaceStore();

  const { agents } = useAgentsStore();
  const safeAgents = Array.isArray(agents) ? agents : [];

  const allConversations = getWorkspaceConversations() ?? [];
  const safeProjects = Array.isArray(projects) ? projects : [];
  const conversations = useMemo(() => allConversations.filter((c) => !c.archived), [allConversations]);
  const isChatRoute = pathname.startsWith(getWorkspacePath(currentWorkspaceId, '/chat'));

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
    createConversation();
    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
  }, [createConversation, router, currentWorkspaceId]);

  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversation(id);
    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
  }, [setActiveConversation, router, currentWorkspaceId]);

  return (
    <CollapsibleSection
      id="chat"
      icon={<MessageSquare size={18} />}
      label="Chat"
      description="Interact with ABI-powered agents"
      href={getWorkspacePath(currentWorkspaceId, '/chat')}
      collapsed={collapsed}
      onNavigate={() => setActiveConversation(null)}
    >
      {/* New Chat button */}
      <button
        onClick={handleNewChat}
        className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <Plus size={12} />
        <span>New Chat</span>
      </button>

      {/* Agents folder */}
      <div className="space-y-0.5">
        <button
          onClick={() => setAgentsExpanded(!agentsExpanded)}
          className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ChevronRight
            size={12}
            className={cn('transition-transform', agentsExpanded && 'rotate-90')}
          />
          <Bot size={12} />
          <span className="flex-1 text-left">Agents</span>
          <span
            onClick={(e) => {
              e.stopPropagation();
              router.push(getWorkspacePath(currentWorkspaceId, '/chat/agents/new'));
            }}
            className="rounded p-0.5 hover:bg-muted"
            title="Create Agent"
          >
            <Plus size={12} />
          </span>
        </button>

        {agentsExpanded && (
          <div className="ml-3 space-y-0.5">
            {safeAgents.filter(agent => agent.enabled).sort((a, b) => a.name.localeCompare(b.name)).map((agent) => {
              const AgentIcon = agentIconComponents[agent.icon] || agentIconComponents.sparkles;
              const isSelected = isChatRoute && selectedAgent === agent.id;

              return (
                <div
                  key={agent.id}
                  className={cn(
                    'group flex items-center gap-1 rounded-md px-1 py-1 text-xs transition-colors',
                    'hover:bg-workspace-accent-10',
                    isSelected && 'bg-workspace-accent-15 font-medium text-workspace-accent'
                  )}
                >
                  <button
                    onClick={() => {
                      setSelectedAgent(agent.id);
                      router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
                    }}
                    className="flex flex-1 items-center gap-1 text-left"
                  >
                    <AgentIcon size={12} className={cn(
                      isSelected ? 'text-workspace-accent' : 'text-muted-foreground'
                    )} />
                    <span className="flex-1 truncate">{agent.name}</span>
                  </button>
                  <button
                    onClick={() => router.push(getWorkspacePath(currentWorkspaceId, `/chat/agents/${agent.id}`))}
                    className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
                    title="Configure agent"
                  >
                    <Settings size={12} className="text-muted-foreground" />
                  </button>
                </div>
              );
            })}
          </div>
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
