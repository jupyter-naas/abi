'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Columns2, Plus, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { ChatInterface } from '@/components/chat/chat-interface';

/**
 * Right AI / compare surface.
 *
 * Renders the same ChatInterface as the central chat panel (bubbles, tool
 * calls, uploads, composer, agent selector) with an independent conversation
 * and agent (defaults to Abi). Open via header Sparkles or ⌘I.
 */
export function AIPane() {
  const [mounted, setMounted] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);
  const isDraggingRef = useRef(false);

  const contextPanelOpen = useWorkspaceStore((s) => s.contextPanelOpen);
  const toggleContextPanel = useWorkspaceStore((s) => s.toggleContextPanel);
  const aiPaneWidth = useWorkspaceStore((s) => s.aiPaneWidth);
  const setAiPaneWidth = useWorkspaceStore((s) => s.setAiPaneWidth);
  const setPaneConversationId = useWorkspaceStore((s) => s.setPaneConversationId);
  const paneAgent = useWorkspaceStore((s) => s.paneAgent);

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
    setPaneConversationId(null);
  };

  if (!mounted || !contextPanelOpen) return null;

  return (
    <>
      {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
      <div
        className="group relative flex w-2 shrink-0 cursor-col-resize items-center justify-center"
        onMouseDown={handleDragStart}
        title="Drag to resize compare pane"
        aria-label="Resize compare pane"
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
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-border/50 px-3">
          <div className="flex min-w-0 items-center gap-2">
            <Columns2 size={16} className="shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">Compare</div>
              <div className="truncate text-[11px] text-muted-foreground">
                Independent thread{paneAgent ? ' · own agent' : ''}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={handleNewChat}
              className={cn(
                'rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="New compare chat"
            >
              <Plus size={16} />
            </button>
            <button
              type="button"
              onClick={toggleContextPanel}
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              style={{ borderRadius: 'var(--org-border-radius, 0px)' }}
              title="Close compare pane"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <ChatInterface surface="pane" />
        </div>
      </aside>
    </>
  );
}
