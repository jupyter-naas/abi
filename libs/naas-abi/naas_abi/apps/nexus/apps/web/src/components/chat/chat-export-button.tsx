'use client';

import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { useWorkspaceStore } from '@/stores/workspace';

interface ChatExportButtonProps {
  className?: string;
}

/**
 * Exports the open conversation. Lives in the shell chrome (desktop Header,
 * mobile top bar) rather than above the composer, so it costs no vertical
 * space in the thread and does not shift the composer when the first message
 * arrives. Reads the store directly so any chrome can render it unwired.
 */
export function ChatExportButton({ className }: ChatExportButtonProps) {
  const [mounted, setMounted] = useState(false);
  const [exporting, setExporting] = useState(false);
  const conversation = useWorkspaceStore(
    (s) => s.conversations.find((c) => c.id === s.activeConversationId) ?? null
  );

  useEffect(() => setMounted(true), []);

  const handleExport = async () => {
    if (!conversation || exporting) return;
    setExporting(true);
    try {
      // Built from local state rather than read back from the server: the PATCH
      // that persists tool calls may still be in flight when the user exports.
      const messagesMetadata = conversation.messages
        .filter((m) => m.role === 'assistant' && (m.toolCalls?.length || m.executionTime !== undefined))
        .map((m) => ({
          message_id: m.id,
          execution_time: m.executionTime ?? null,
          steps: (m.toolCalls ?? []).map((t) => ({
            tool_name: t.toolName,
            prefix: t.prefix,
            status: t.status,
            input: t.input ?? null,
            output: t.output ?? null,
          })),
          sources: m.sources ?? [],
        }));

      const response = await authFetch(
        `${getApiUrl()}/api/chat/conversations/${conversation.id}/export`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ format: 'txt', messages_metadata: messagesMetadata }),
        }
      );

      if (!response.ok) throw new Error('Failed to export conversation');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `conversation-${conversation.id}-${Date.now()}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export conversation. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  // Nothing to export until a thread has content, and the store only holds
  // conversations after hydration, so stay absent on the server pass.
  if (!mounted || !conversation || conversation.messages.length === 0) return null;

  return (
    <button
      type="button"
      onClick={handleExport}
      disabled={exporting}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
        'text-muted-foreground hover:bg-muted hover:text-foreground',
        exporting && 'cursor-wait opacity-60',
        className
      )}
      title="Export conversation"
      aria-label="Export conversation"
    >
      {exporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
    </button>
  );
}
