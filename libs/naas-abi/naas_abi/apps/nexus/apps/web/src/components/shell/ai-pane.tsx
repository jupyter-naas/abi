'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { History, MessageSquare, MoreHorizontal, Plus, Presentation, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { downloadConversationTranscript } from '@/lib/chat-transcript-export';
import { pickSlidesAgentId } from '@/lib/create-slides-project';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAgentsStore } from '@/stores/agents';
import { useSlidesStore } from '@/stores/slides';
import { ChatInterface } from '@/components/chat/chat-interface';

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
  const pathname = usePathname();

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
  const slidesSlug = useSlidesStore((s) => s.selectedSlug);
  const slidesTitle = useSlidesStore((s) => s.selectedTitle);
  const slidesMode = useSlidesStore((s) => s.editorMode);
  const slidesRuntimeStatus = useSlidesStore((s) => s.runtimeStatus);
  const isSlidesRoute = typeof pathname === 'string' && pathname.includes('/slides');
  const slidesContext =
    isSlidesRoute && slidesSlug
      ? {
          slug: slidesSlug,
          title: slidesTitle || slidesSlug,
          mode: slidesMode,
          branch: `slides/${slidesSlug}`,
          path: `slides/${slidesSlug}/deck.html`,
          runtime: slidesRuntimeStatus,
        }
      : null;

  useEffect(() => {
    setMounted(true);
  }, []);

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
    // New blank pane chat: bind Slides on /slides, else Abi, unless the user
    // picked another agent in the selector (history tabs are not an explicit pick).
    if (!ws.paneAgentExplicitlySelected) {
      const agents = useAgentsStore.getState().agents;
      const onSlides = typeof pathname === 'string' && pathname.includes('/slides');
      const boundId = onSlides
        ? pickSlidesAgentId(agents)
        : (agents.find(
            (a) =>
              a.enabled &&
              (a.name === 'Abi' ||
                (typeof a.class_name === 'string' &&
                  a.class_name.toLowerCase().includes('abiagent'))),
          ) ??
          agents.find((a) => a.isDefault && a.enabled) ??
          agents.find((a) => a.enabled))?.id;
      if (boundId) ws.setPaneAgent(boundId);
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
      <div
        className="group relative flex w-2 shrink-0 cursor-col-resize items-center justify-center"
        onMouseDown={handleDragStart}
        title="Drag to resize chat pane"
        aria-label="Resize chat pane"
        role="separator"
        aria-orientation="vertical"
      >
        <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-workspace-accent" />
        <div className="relative z-10 flex flex-col gap-[5px]">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-[3px] w-[3px] rounded-full bg-muted-foreground/40 transition-colors group-hover:bg-workspace-accent"
            />
          ))}
        </div>
      </div>
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
              <button
                type="button"
                role="tab"
                aria-selected
                className={cn(
                  'group/tab relative flex max-w-[160px] shrink-0 items-center gap-1.5 border-r border-border/50 px-3 text-xs',
                  'bg-background text-foreground'
                )}
              >
                <span className="truncate font-medium">New chat</span>
              </button>
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
        {slidesContext && (
          <div className="flex shrink-0 items-center gap-2 border-b border-border/50 bg-muted/30 px-3 py-1.5 text-[11px] text-muted-foreground">
            <Presentation size={12} className="shrink-0 text-workspace-accent" />
            <span className="min-w-0 truncate">
              Editing{' '}
              <span className="font-medium text-foreground">
                {slidesContext.title || slidesContext.slug}
              </span>
              {' · '}
              {slidesContext.path}
              {slidesContext.runtime === 'error' || slidesContext.runtime === 'degraded'
                ? ' · Forgejo fallback'
                : slidesContext.runtime === 'ready'
                  ? ' · workspace'
                  : ''}
            </span>
          </div>
        )}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <ChatInterface surface="pane" />
        </div>
      </aside>
    </>
  );
}
