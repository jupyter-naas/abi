'use client';

import React, { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { MessageSquare, ChevronRight, Plus, Pin, Folder, MoreVertical, Bot, Archive, Edit2, Trash2, LayoutGrid, List } from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

// ─── Logo resolution ──────────────────────────────────────────────────────────
// Returns { url, invert } where invert=true means the image is monochrome and
// needs CSS `dark:invert` so it stays visible on dark backgrounds.
const LOGO_MAP: { pattern: RegExp; url: string; invert?: boolean }[] = [
  // Simple Icons CDN (high-quality SVG, monochrome → needs invert in dark mode)
  { pattern: /openai|gpt-?[34]|gpt-?4o|o1|o3|o4/i,     url: 'https://cdn.simpleicons.org/openai',       invert: true  },
  { pattern: /claude|anthropic/i,                         url: 'https://cdn.simpleicons.org/anthropic',    invert: true  },
  { pattern: /gemini|gemma/i,                             url: 'https://cdn.simpleicons.org/googlegemini'               },
  { pattern: /llama|meta:/i,                              url: 'https://cdn.simpleicons.org/meta',         invert: true  },
  { pattern: /perplexity/i,                               url: 'https://cdn.simpleicons.org/perplexity',  invert: true  },
  { pattern: /ollama/i,                                   url: 'https://cdn.simpleicons.org/ollama',       invert: true  },
  // Direct favicons (already coloured, no invert needed)
  { pattern: /mistral|mixtral/i,                          url: 'https://mistral.ai/favicon.ico'                         },
  { pattern: /deepseek/i,                                 url: 'https://www.deepseek.com/favicon.ico'                   },
  { pattern: /grok|xai|x\.ai/i,                          url: 'https://x.ai/favicon.ico',                invert: true  },
  { pattern: /openrouter/i,                               url: 'https://openrouter.ai/favicon.ico'                      },
  { pattern: /groq/i,                                     url: 'https://groq.com/favicon.ico'                           },
  { pattern: /qwen/i,                                     url: 'https://www.google.com/s2/favicons?sz=64&domain=qwenlm.github.io' },
  { pattern: /cohere/i,                                   url: 'https://cohere.com/favicon.ico'                         },
  { pattern: /amazon|bedrock|nova/i,                      url: 'https://www.google.com/s2/favicons?sz=64&domain=aws.amazon.com' },
];

function resolveAgentLogo(name: string, logoUrl: string | null): { url: string; invert: boolean } | null {
  if (logoUrl) return { url: logoUrl, invert: false };
  for (const { pattern, url, invert } of LOGO_MAP) {
    if (pattern.test(name)) return { url, invert: !!invert };
  }
  return null;
}

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
  const [agentView, setAgentView] = useState<'list' | 'grid'>('list');
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
        <div className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground">
          <button
            onClick={() => setAgentsExpanded(!agentsExpanded)}
            className="flex items-center justify-center rounded p-0.5 hover:bg-muted hover:text-foreground"
            aria-expanded={agentsExpanded}
          >
            <ChevronRight
              size={12}
              className={cn('transition-transform', agentsExpanded && 'rotate-90')}
            />
          </button>
          <Link
            href={getWorkspacePath(currentWorkspaceId, '/settings/agents')}
            className="flex flex-1 items-center gap-1 rounded py-0.5 text-left hover:text-foreground"
          >
            <Bot size={12} />
            <span>Agents</span>
          </Link>
          {/* View toggle: list ↔ grid */}
          <button
            onClick={() => setAgentView(agentView === 'list' ? 'grid' : 'list')}
            className="rounded p-0.5 hover:bg-muted hover:text-foreground"
            title={agentView === 'list' ? 'Switch to grid view' : 'Switch to list view'}
          >
            {agentView === 'list' ? <LayoutGrid size={12} /> : <List size={12} />}
          </button>
          <Link
            href={getWorkspacePath(currentWorkspaceId, '/chat/agents/new')}
            className="rounded p-0.5 hover:bg-muted hover:text-foreground"
            title="Create Agent"
          >
            <Plus size={12} />
          </Link>
        </div>

        {agentsExpanded && agentView === 'list' && (
          <div className="ml-3 space-y-0.5">
            {safeAgents.filter(agent => agent.enabled).sort((a, b) => a.name.localeCompare(b.name)).map((agent) => {
              const isSelected = isChatRoute && selectedAgent === agent.id;
              const logo = resolveAgentLogo(agent.name, agent.logoUrl ?? null);
              const initials = agent.name
                .split(/[\s\-_]+/)
                .slice(0, 2)
                .map((w: string) => w[0]?.toUpperCase() ?? '')
                .join('');
              const hue = agent.name.split('').reduce((acc: number, c: string) => acc + c.charCodeAt(0), 0) % 360;

              return (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgent(agent.id);
                    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
                  }}
                  className={cn(
                    'group flex w-full items-center gap-1.5 rounded-md px-1 py-1 text-left text-xs transition-colors',
                    'hover:bg-workspace-accent-10',
                    isSelected && 'bg-workspace-accent-15 text-workspace-accent'
                  )}
                >
                  <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center overflow-hidden rounded">
                    {logo ? (
                      <img
                        src={logo.url}
                        alt=""
                        className={cn('h-4 w-4 object-contain', logo.invert && 'dark:invert')}
                      />
                    ) : (
                      <span
                        className="flex h-4 w-4 items-center justify-center rounded text-[8px] font-bold text-white"
                        style={{ background: `hsl(${hue} 55% 50%)` }}
                      >
                        {initials}
                      </span>
                    )}
                  </span>
                  <span className="flex-1 truncate">{agent.name}</span>
                </button>
              );
            })}
          </div>
        )}

        {agentsExpanded && agentView === 'grid' && (
          <div className="ml-1 grid grid-cols-3 gap-1 pt-0.5">
            {safeAgents.filter(agent => agent.enabled).sort((a, b) => a.name.localeCompare(b.name)).map((agent) => {
              const isSelected = isChatRoute && selectedAgent === agent.id;
              const logo = resolveAgentLogo(agent.name, agent.logoUrl ?? null);
              const initials = agent.name
                .split(/[\s\-_]+/)
                .slice(0, 2)
                .map((w: string) => w[0]?.toUpperCase() ?? '')
                .join('');
              const hue = agent.name.split('').reduce((acc: number, c: string) => acc + c.charCodeAt(0), 0) % 360;

              return (
                <button
                  key={agent.id}
                  onClick={() => {
                    setSelectedAgent(agent.id);
                    router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
                  }}
                  title={agent.name}
                  className={cn(
                    'group flex flex-col items-center gap-1 rounded-md px-1 py-2 text-center text-[10px] transition-colors',
                    'hover:bg-workspace-accent-10',
                    isSelected && 'bg-workspace-accent-15 text-workspace-accent'
                  )}
                >
                  {/* Big logo */}
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg">
                    {logo ? (
                      <img
                        src={logo.url}
                        alt=""
                        className={cn('h-8 w-8 object-contain', logo.invert && 'dark:invert')}
                      />
                    ) : (
                      <span
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
                        style={{ background: `hsl(${hue} 55% 50%)` }}
                      >
                        {initials}
                      </span>
                    )}
                  </span>
                  <span className="w-full truncate leading-tight">{agent.name.split(/[\s:\/]+/)[0]}</span>
                </button>
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
