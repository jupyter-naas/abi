'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { MessageSquare, Settings, ChevronRight, Pin, Archive, Edit2, Trash2, MoreVertical, FileText, Save } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useProjectsStore } from '@/stores/projects';
import { ChatInterface } from '@/components/chat/chat-interface';

interface ProjectPageProps {
  modulePath: string;
}

const INSTRUCTIONS_STORAGE_KEY = (modulePath: string) =>
  `nexus-project-instructions:${modulePath}`;

function useProjectInstructions(modulePath: string) {
  const [instructions, setInstructions] = useState('');

  useEffect(() => {
    try {
      const stored = localStorage.getItem(INSTRUCTIONS_STORAGE_KEY(modulePath));
      if (stored) setInstructions(stored);
    } catch {
      // ignore
    }
  }, [modulePath]);

  const saveInstructions = useCallback(
    (value: string) => {
      setInstructions(value);
      try {
        localStorage.setItem(INSTRUCTIONS_STORAGE_KEY(modulePath), value);
      } catch {
        // ignore
      }
    },
    [modulePath]
  );

  return { instructions, saveInstructions };
}

function ConversationListItem({
  id,
  title,
  pinned,
  isActive,
  onClick,
  onPin,
  onArchive,
  onRename,
  onDelete,
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
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [editValue, setEditValue] = useState(title);

  const handleRenameSubmit = () => {
    if (editValue.trim() && editValue !== title) {
      onRename(editValue.trim());
    }
    setIsRenaming(false);
  };

  if (isRenaming) {
    return (
      <div className="flex items-center gap-2 rounded-md px-3 py-2">
        <MessageSquare size={14} className="flex-shrink-0 text-muted-foreground" />
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleRenameSubmit();
            else if (e.key === 'Escape') setIsRenaming(false);
          }}
          onBlur={handleRenameSubmit}
          autoFocus
          className="flex-1 bg-transparent text-sm outline-none border-b border-workspace-accent"
        />
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={onClick}
        className={cn(
          'group flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
          'hover:bg-accent',
          isActive && 'bg-accent text-foreground font-medium'
        )}
      >
        {pinned && <Pin size={12} className="flex-shrink-0 text-workspace-accent" />}
        <MessageSquare size={14} className="flex-shrink-0 text-muted-foreground" />
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
      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-md border border-border bg-popover p-1 shadow-lg">
            <button
              onClick={(e) => { e.stopPropagation(); onPin(); setShowMenu(false); }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Pin size={12} /> {pinned ? 'Unpin' : 'Pin'}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setIsRenaming(true); setShowMenu(false); }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Edit2 size={12} /> Rename
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onArchive(); setShowMenu(false); }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Archive size={12} /> Archive
            </button>
            <div className="my-1 h-px bg-border" />
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); setShowMenu(false); }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10"
            >
              <Trash2 size={12} /> Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function ProjectPage({ modulePath }: ProjectPageProps) {
  const [showSettings, setShowSettings] = useState(false);
  const [editingInstructions, setEditingInstructions] = useState('');

  const { projects, fetchProjects } = useProjectsStore();
  const {
    activeConversationId,
    setActiveConversation,
    currentWorkspaceId,
    getWorkspaceConversations,
    togglePinConversation,
    toggleArchiveConversation,
    renameConversation,
    deleteConversation,
    syncWorkspaceConversations,
  } = useWorkspaceStore();

  const { instructions, saveInstructions } = useProjectInstructions(modulePath);

  const project = projects.find((p) => p.module_path === modulePath);

  useEffect(() => {
    if (currentWorkspaceId) {
      void fetchProjects(currentWorkspaceId);
      void syncWorkspaceConversations(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchProjects, syncWorkspaceConversations]);

  // Open instructions panel when opening settings
  useEffect(() => {
    if (showSettings) {
      setEditingInstructions(instructions);
    }
  }, [showSettings, instructions]);

  const allConversations = useMemo(() => getWorkspaceConversations() ?? [], [getWorkspaceConversations]);

  const moduleConversations = useMemo(
    () =>
      allConversations
        .filter((c) => c.modulePath === modulePath && !c.archived && !c.isDraft)
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()),
    [allConversations, modulePath]
  );

  const handleSelectConversation = useCallback(
    (id: string) => {
      setActiveConversation(id);
    },
    [setActiveConversation]
  );

  const handleNewChat = useCallback(() => {
    setActiveConversation(null);
  }, [setActiveConversation]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main area: chat + conversation history */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Project header bar */}
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">
              {project?.name ?? modulePath.split('.').pop()}
            </span>
            {project?.description && (
              <span className="text-xs text-muted-foreground truncate max-w-xs hidden md:block">
                {project.description}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewChat}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            >
              New chat
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={cn(
                'rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors',
                showSettings && 'bg-accent text-foreground'
              )}
              title="Project settings"
            >
              <Settings size={14} />
            </button>
          </div>
        </div>

        {/* Chat interface */}
        <div className="flex-1 overflow-hidden">
          <ChatInterface
            modulePath={modulePath}
            moduleInstructions={instructions || undefined}
          />
        </div>

        {/* Past conversations */}
        {moduleConversations.length > 0 && (
          <div className="border-t border-border">
            <div className="px-4 py-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Past conversations
              </p>
              <div className="space-y-0.5 max-h-40 overflow-y-auto">
                {moduleConversations.map((conv) => (
                  <ConversationListItem
                    key={conv.id}
                    id={conv.id}
                    title={conv.title}
                    pinned={conv.pinned}
                    isActive={activeConversationId === conv.id}
                    onClick={() => handleSelectConversation(conv.id)}
                    onPin={() => togglePinConversation(conv.id)}
                    onArchive={() => toggleArchiveConversation(conv.id)}
                    onRename={(newTitle) => renameConversation(conv.id, newTitle)}
                    onDelete={() => {
                      if (confirm(`Delete "${conv.title}"?`)) {
                        deleteConversation(conv.id);
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Instructions panel (right side) */}
      {showSettings && (
        <div className="w-72 border-l border-border flex flex-col bg-background">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FileText size={14} />
              Instructions
            </div>
            <button
              onClick={() => setShowSettings(false)}
              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <ChevronRight size={14} />
            </button>
          </div>
          <div className="flex flex-1 flex-col p-3 gap-3">
            <p className="text-xs text-muted-foreground">
              Instructions guide this project's agents. They are prepended to every conversation in this project.
            </p>
            <textarea
              value={editingInstructions}
              onChange={(e) => setEditingInstructions(e.target.value)}
              placeholder="e.g. You are a financial analyst assistant. Always format numbers with thousands separators..."
              className="flex-1 min-h-[200px] resize-none rounded-md border border-border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-workspace-accent/30"
            />
            <button
              onClick={() => {
                saveInstructions(editingInstructions);
                setShowSettings(false);
              }}
              className="flex items-center justify-center gap-2 rounded-md bg-workspace-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90 transition-opacity"
            >
              <Save size={14} />
              Save instructions
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
