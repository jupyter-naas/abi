'use client';

import { useEffect, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  downloadConversationTranscript,
  type TranscriptFormat,
} from '@/lib/chat-transcript-export';
import { useWorkspaceStore } from '@/stores/workspace';

interface ChatExportButtonProps {
  className?: string;
  /**
   * Conversation to export. Defaults to the central thread
   * (`activeConversationId`). Pass `paneConversationId` from the AI pane.
   */
  conversationId?: string | null;
}

/**
 * Overflow menu for conversation export. Lives in shell chrome (desktop Header,
 * mobile top bar, AI pane controls) so it costs no vertical space in the thread.
 * Uses the same client transcript helpers as the right AI pane.
 */
export function ChatExportButton({ className, conversationId }: ChatExportButtonProps) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const activeConversationId = useWorkspaceStore((s) => s.activeConversationId);
  const resolvedId = conversationId !== undefined ? conversationId : activeConversationId;
  const conversation = useWorkspaceStore(
    (s) => (resolvedId ? s.conversations.find((c) => c.id === resolvedId) ?? null : null)
  );

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const canExport = Boolean(
    conversation && conversation.messages.some((m) => m.role === 'user' || m.role === 'assistant')
  );

  const handleExport = (format: TranscriptFormat) => {
    if (!conversation || !canExport) return;
    downloadConversationTranscript(
      {
        id: conversation.id,
        title: conversation.title,
        workspaceId: conversation.workspaceId,
        messages: conversation.messages.map((m) => ({
          role: m.role,
          content: m.content,
          agent: m.agent,
          timestamp: m.timestamp,
        })),
      },
      format
    );
    setOpen(false);
  };

  // Store only holds conversations after hydration; stay absent on the server pass
  // and when no thread is selected.
  if (!mounted || !conversation) return null;

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
          'text-muted-foreground hover:bg-muted hover:text-foreground',
          open && 'bg-muted text-foreground'
        )}
        title="More"
        aria-label="More chat actions"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <MoreHorizontal size={16} />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Chat actions"
          className="absolute right-0 top-full z-40 mt-1 w-52 rounded-md border border-border bg-popover py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            disabled={!canExport}
            onClick={() => handleExport('md')}
            className={cn(
              'flex w-full px-3 py-2 text-left text-xs transition-colors',
              canExport
                ? 'text-foreground hover:bg-muted'
                : 'cursor-not-allowed text-muted-foreground'
            )}
          >
            Export transcript
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={!canExport}
            onClick={() => handleExport('txt')}
            className={cn(
              'flex w-full px-3 py-2 text-left text-xs transition-colors',
              canExport
                ? 'text-foreground hover:bg-muted'
                : 'cursor-not-allowed text-muted-foreground'
            )}
          >
            Export as text
          </button>
        </div>
      )}
    </div>
  );
}
