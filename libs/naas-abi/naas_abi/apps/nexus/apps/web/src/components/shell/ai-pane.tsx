'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { History, MessageSquare, MoreHorizontal, Plus, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { downloadConversationTranscript } from '@/lib/chat-transcript-export';
import { usePathname } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useFeaturePaneStore } from '@/stores/feature-pane';
import { useSlidesStore } from '@/stores/slides';
import { bindFeaturePaneAgent } from '@/lib/feature-agent-pane';
import { featureOpenResource, getPaneSurfaceForPath } from '@/lib/feature-office-agents';
import { pickFeaturePaneAgent } from '@/lib/pick-workspace-default-agent';
import { ColumnResizeHandle } from './column-resize-handle';
import dynamic from 'next/dynamic';

const ChatInterface = dynamic(
  () => import('@/components/chat/chat-interface').then((m) => m.ChatInterface),
  { ssr: false },
);

/**
 * Right chat pane: same ChatInterface as the central panel, with Cursor-like
 * open-chat tabs and a history clock. Side-by-side compare stays available by
 * keeping this pane open next to the main thread (⌘K / Sparkles).
 */
export function AIPane() {
  const [mounted, setMounted] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showOverflow, setShowOverflow] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);
  const isDraggingRef = useRef(false);
  const controlsRef = useRef<HTMLDivElement>(null);

  const contextPanelOpen = useWorkspaceStore((s) => s.contextPanelOpen);
  const toggleContextPanel = useWorkspaceStore((s) => s.toggleContextPanel);
  const aiPaneWidth = useWorkspaceStore((s) => s.aiPaneWidth);
  const setAiPaneWidth = useWorkspaceStore((s) => s.setAiPaneWidth);
  const paneConversationId = useWorkspaceStore((s) => s.paneConversationId);
  const setPaneConversationId = useWorkspaceStore((s) => s.setPaneConversationId);
  const paneOpenTabIds = useWorkspaceStore((s) => s.paneOpenTabIds);
  const openPaneTab = useWorkspaceStore((s) => s.openPaneTab);
  const closePaneTab = useWorkspaceStore((s) => s.closePaneTab);
  const conversations = useWorkspaceStore((s) => s.conversations);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Bind the agent of the section the pane opens on (Apps on /apps, Slides
  // on a deck, ...). Home, Chat, and sections without one get the workspace
  // default (Abi when there is none). An open item (deck, app, dataset)
  // forces it over a picker choice.
  const pathname = usePathname();
  const surface = getPaneSurfaceForPath(pathname);
  const slidesSlug = useSlidesStore((s) => s.selectedSlug);
  const featureResource = useFeaturePaneStore((s) => s.resource);
  const agents = useAgentsStore((s) => s.agents);
  const openItemId =
    surface === 'slides'
      ? slidesSlug
      : (featureOpenResource(pathname, featureResource)?.id ?? null);
  useEffect(() => {
    if (!contextPanelOpen) return;
    bindFeaturePaneAgent(surface, { force: Boolean(openItemId) });
  }, [contextPanelOpen, surface, openItemId, agents]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = dragStartX.current - e.clientX;
      setAiPaneWidth(dragStartWidth.current + delta);
    };
    const onUp = () => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [setAiPaneWidth]);

  useEffect(() => {
    if (!showHistory && !showOverflow) return;
    const onDown = (e: MouseEvent) => {
      if (controlsRef.current && !controlsRef.current.contains(e.target as Node)) {
        setShowHistory(false);
        setShowOverflow(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [showHistory, showOverflow]);

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartX.current = e.clientX;
      dragStartWidth.current = aiPaneWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [aiPaneWidth]
  );

  const handleNewChat = () => {
    const ws = useWorkspaceStore.getState();
    setPaneConversationId(null);
    // New blank pane chat: restore this section's agent (or the workspace
    // default) unless the user picked another agent in the selector
    // (history tabs must not count as an explicit pick).
    if (!ws.paneAgentExplicitlySelected) {
      const preferred = pickFeaturePaneAgent(useAgentsStore.getState().agents, surface);
      if (preferred) ws.setPaneAgent(preferred.id);
    }
    setShowHistory(false);
    setShowOverflow(false);
  };

  const paneConversation = useMemo(() => {
    if (!paneConversationId) return null;
    return conversations.find((c) => c.id === paneConversationId) ?? null;
  }, [paneConversationId, conversations]);

  const canExportTranscript = Boolean(
    paneConversation && paneConversation.messages.some((m) => m.role === 'user' || m.role === 'assistant')
  );

  const handleExportTranscript = (format: 'md' | 'txt') => {
    if (!paneConversation || !canExportTranscript) return;
    downloadConversationTranscript(
      {
        id: paneConversation.id,
        title: paneConversation.title,
        workspaceId: paneConversation.workspaceId,
        messages: paneConversation.messages.map((m) => ({
          role: m.role,
          content: m.content,
          agent: m.agent,
          timestamp: m.timestamp,
        })),
      },
      format
    );
    setShowOverflow(false);
  };

  const openTabs = useMemo(() => {
    return paneOpenTabIds
      .map((id) => conversations.find((c) => c.id === id))
      .filter((c): c is NonNullable<typeof c> => Boolean(c));
  }, [paneOpenTabIds, conversations]);

  const recentConversations = useMemo(() => {
    if (!currentWorkspaceId) return [];
    return conversations
      .filter((c) => c.workspaceId === currentWorkspaceId && !c.archived)
      .slice()
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, 30);
  }, [conversations, currentWorkspaceId]);

  const showNewChatTab = paneConversationId === null;

  if (!mounted || !contextPanelOpen) return null;

  return (
    <>
      {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
      <ColumnResizeHandle onMouseDown={handleDragStart} label="Drag to resize chat pane" isActive={isDragging} />
      <aside
        className="flex h-full shrink-0 flex-col border-l border-border/50 bg-background"
        style={{ width: aiPaneWidth }}
        data-ai-pane="true"
      >
        <div className="flex h-10 shrink-0 items-stretch border-b border-border/50">
          <div
            className="flex min-w-0 flex-1 items-stretch overflow-x-auto"
            role="tablist"
            aria-label="Open chats"
          >
            {showNewChatTab && (
              <div
                role="tab"
                aria-selected
                className={cn(
                  'group/tab relative flex max-w-[160px] shrink-0 items-center gap-1 border-r border-border/50 pl-3 pr-1 text-xs',
                  'bg-background text-foreground'
                )}
              >
                <span className="flex min-w-0 flex-1 items-center gap-1.5 py-2">
                  <MessageSquare size={12} className="shrink-0 text-muted-foreground" />
                  <span className="truncate font-medium">New chat</span>
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleContextPanel();
                  }}
                  className="rounded p-0.5 text-muted-foreground opacity-70 transition-opacity hover:bg-muted hover:text-foreground group-hover/tab:opacity-100 focus-visible:opacity-100"
                  style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
                  title="Close chat pane"
                  aria-label="Close chat pane"
                >
                  <X size={12} />
                </button>
              </div>
            )}
            {openTabs.map((tab) => {
              const active = paneConversationId === tab.id;
              return (
                <div
                  key={tab.id}
                  role="tab"
                  aria-selected={active}
                  className={cn(
                    'group/tab relative flex max-w-[160px] shrink-0 items-center gap-1 border-r border-border/50 pl-3 pr-1 text-xs',
                    active
                      ? 'bg-background text-foreground'
                      : 'bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                  )}
                >
                  <button
                    type="button"
                    onClick={() => openPaneTab(tab.id)}
                    className="min-w-0 flex-1 truncate py-2 text-left font-medium"
                    title={tab.title}
                  >
                    {tab.title || 'Chat'}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      closePaneTab(tab.id);
                    }}
                    className={cn(
                      'rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground',
                      'group-hover/tab:opacity-100 focus-visible:opacity-100',
                      active && 'opacity-70'
                    )}
                    style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
                    title="Close tab"
                    aria-label={`Close ${tab.title || 'chat'}`}
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })}
          </div>

          <div className="relative flex shrink-0 items-center gap-0.5 px-1.5" ref={controlsRef}>
            <button
              type="button"
              onClick={handleNewChat}
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="New chat"
              aria-label="New chat"
            >
              <Plus size={16} />
            </button>
            <button
              type="button"
              onClick={() => {
                setShowOverflow(false);
                setShowHistory((v) => !v);
              }}
              className={cn(
                'rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground',
                showHistory && 'bg-muted text-foreground'
              )}
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="Chat history"
              aria-label="Chat history"
              aria-expanded={showHistory}
            >
              <History size={16} />
            </button>
            <button
              type="button"
              onClick={() => {
                setShowHistory(false);
                setShowOverflow((v) => !v);
              }}
              className={cn(
                'rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground',
                showOverflow && 'bg-muted text-foreground'
              )}
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="More"
              aria-label="More chat actions"
              aria-expanded={showOverflow}
              aria-haspopup="menu"
            >
              <MoreHorizontal size={16} />
            </button>
            <button
              type="button"
              onClick={toggleContextPanel}
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="Close chat pane"
              aria-label="Close chat pane"
            >
              <X size={16} />
            </button>

            {showHistory && (
              <div className="absolute right-1 top-full z-40 mt-1 w-72 max-h-80 overflow-auto rounded-md border border-border bg-popover py-1 shadow-lg">
                <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Recent
                </div>
                {recentConversations.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">No chat history yet</p>
                ) : (
                  recentConversations.map((conv) => {
                    const isActive = paneConversationId === conv.id;
                    const isOpen = paneOpenTabIds.includes(conv.id);
                    return (
                      <button
                        key={conv.id}
                        type="button"
                        onClick={() => {
                          openPaneTab(conv.id);
                          setShowHistory(false);
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors',
                          'hover:bg-muted',
                          isActive && 'bg-muted'
                        )}
                      >
                        <MessageSquare
                          size={12}
                          className={cn(
                            'shrink-0',
                            isOpen ? 'text-workspace-accent' : 'text-muted-foreground'
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate">{conv.title || 'Chat'}</span>
                      </button>
                    );
                  })
                )}
              </div>
            )}

            {showOverflow && (
              <div
                role="menu"
                aria-label="Chat actions"
                className="absolute right-1 top-full z-40 mt-1 w-52 rounded-md border border-border bg-popover py-1 shadow-lg"
              >
                <button
                  type="button"
                  role="menuitem"
                  disabled={!canExportTranscript}
                  onClick={() => handleExportTranscript('md')}
                  className={cn(
                    'flex w-full px-3 py-2 text-left text-xs transition-colors',
                    canExportTranscript
                      ? 'text-foreground hover:bg-muted'
                      : 'cursor-not-allowed text-muted-foreground'
                  )}
                >
                  Export transcript
                </button>
                <button
                  type="button"
                  role="menuitem"
                  disabled={!canExportTranscript}
                  onClick={() => handleExportTranscript('txt')}
                  className={cn(
                    'flex w-full px-3 py-2 text-left text-xs transition-colors',
                    canExportTranscript
                      ? 'text-foreground hover:bg-muted'
                      : 'cursor-not-allowed text-muted-foreground'
                  )}
                >
                  Export as text
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <ChatInterface surface="pane" />
        </div>
      </aside>
    </>
  );
}
