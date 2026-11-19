'use client';

import { useState } from 'react';
import { ArrowLeft, Check, Copy, Loader2, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '../card';
import { buildChatExportText, FEEDBACK_TYPE_LABELS } from '../chat-export';
import { formatDateTime } from '../format';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsScope } from '../scope';
import type { ChatDetail, ChatMessage, ChatMessageStep } from '../types';

const buttonClass = cn(
  'flex h-9 items-center gap-1.5 border border-border bg-card px-2.5 text-sm text-foreground transition-colors',
  'hover:border-foreground/20 hover:bg-muted/40 disabled:opacity-60'
);

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
    } finally {
      document.body.removeChild(ta);
    }
  }
}

/**
 * One conversation's messages (`GET {base}/analytics/chats/{id}`). Opened only for a caller
 * who may read them (`can_read_conversations`); the API still answers 403 to anyone else.
 */
export function ChatDetailView({
  scope,
  conversationId,
  timeZone,
  onClose,
}: {
  scope: AnalyticsScope;
  conversationId: string;
  timeZone: string;
  onClose: () => void;
}) {
  const { data, loading, error, status } = useAnalytics<ChatDetail>(
    scope,
    `/chats/${encodeURIComponent(conversationId)}`,
    null
  );
  const [copying, setCopying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const handleCopy = async () => {
    if (!data) return;
    setCopyError(null);
    setCopying(true);
    try {
      await copyText(buildChatExportText(data));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      setCopyError(e instanceof Error ? e.message : String(e));
    } finally {
      setCopying(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div className="flex min-w-0 items-center gap-3">
          <button type="button" onClick={onClose} className={buttonClass} title="Back to the conversations">
            <ArrowLeft size={14} />
            <span>Back</span>
          </button>
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Conversation</div>
            <div className="truncate font-mono text-sm font-medium text-foreground">{conversationId}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {copyError && <span className="text-xs text-destructive">{copyError}</span>}
          <button
            type="button"
            onClick={() => void handleCopy()}
            disabled={copying || !data}
            className={buttonClass}
            title="Copy as text"
          >
            {copying ? <Loader2 size={14} className="animate-spin" /> : copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className={cn(buttonClass, 'w-9 justify-center px-0')}
            title="Close"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {loading && !data && <LoadingBlock label="Loading conversation" />}
      {error && (
        <ErrorBlock
          message={
            status === 403
              ? "You may see this conversation's figures, not its messages."
              : status === 404
                ? 'This conversation is not in this scope.'
                : error
          }
        />
      )}
      {data && (
        <Card title={data.title || conversationId} subtitle={`${data.messages.length} message(s) · agent: ${data.agent}`}>
          {data.messages.length === 0 ? (
            <EmptyBlock>Conversation has no stored messages.</EmptyBlock>
          ) : (
            <div className="space-y-4">
              {data.messages.map((m) => (
                <ChatMessageBubble key={m.id} message={m} timeZone={timeZone} />
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function ChatMessageBubble({ message, timeZone }: { message: ChatMessage; timeZone: string }) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const isSystem = message.role === 'system';

  const bubble = cn(
    'max-w-[85%] whitespace-pre-wrap break-words border px-3 py-2 text-sm text-foreground',
    isUser && 'border-primary/30 bg-primary/5',
    isAssistant && 'border-border bg-background',
    isSystem && 'border-border/60 bg-muted/40 text-muted-foreground'
  );

  const steps = message.metadata?.steps ?? [];
  const executionTime = message.metadata?.execution_time;
  const feedback = message.metadata?.feedback;
  const feedbackType = message.metadata?.feedback_type;
  const feedbackDetail = message.metadata?.feedback_detail;
  const feedbackSeverity = message.metadata?.feedback_severity;
  const hasFeedbackDetails =
    isAssistant &&
    feedback === 'dislike' &&
    ((typeof feedbackType === 'string' && feedbackType) ||
      (typeof feedbackDetail === 'string' && feedbackDetail) ||
      typeof feedbackSeverity === 'number');

  return (
    <div className={cn('flex flex-col gap-1', isUser ? 'items-end' : 'items-start')}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-muted-foreground">
        <span className="font-semibold">{message.role}</span>
        {message.agent && <span>· {message.agent}</span>}
        {message.created_at && <span>· {formatDateTime(message.created_at, timeZone)}</span>}
        {typeof executionTime === 'number' && executionTime > 0 && <span>· {executionTime.toFixed(1)}s</span>}
        {isAssistant && feedback === 'like' && (
          <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
            <ThumbsUp size={10} fill="currentColor" strokeWidth={1.5} />
            Liked
          </span>
        )}
        {isAssistant && feedback === 'dislike' && (
          <span className="inline-flex items-center gap-1 rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-destructive">
            <ThumbsDown size={10} fill="currentColor" strokeWidth={1.5} />
            Disliked
          </span>
        )}
      </div>
      {steps.length > 0 && <ChatStepsList steps={steps} alignEnd={isUser} />}
      <div className={bubble}>{message.content || <span className="opacity-50">(empty)</span>}</div>
      {hasFeedbackDetails && (
        <div className="max-w-[85%] space-y-1 border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-foreground">
          {typeof feedbackType === 'string' && feedbackType && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-destructive">Type:</span>{' '}
              {FEEDBACK_TYPE_LABELS[feedbackType] ?? feedbackType}
            </div>
          )}
          {typeof feedbackSeverity === 'number' && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-destructive">Severity:</span>{' '}
              {feedbackSeverity}/5
            </div>
          )}
          {typeof feedbackDetail === 'string' && feedbackDetail && (
            <div className="whitespace-pre-wrap">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-destructive">Detail:</span>{' '}
              {feedbackDetail}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChatStepsList({ steps, alignEnd }: { steps: ChatMessageStep[]; alignEnd: boolean }) {
  return (
    <div className={cn('flex max-w-[85%] flex-col gap-1', alignEnd && 'items-end')}>
      <ul className="w-full space-y-1.5 border border-border/60 bg-background/60 p-2 text-xs">
        {steps.map((s, i) => (
          <li key={i} className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {s.prefix}
              </span>
              <span className="font-medium text-foreground">{s.tool_name}</span>
              <span
                className={cn(
                  'ml-auto text-[10px] uppercase tracking-wide text-muted-foreground',
                  s.status === 'done' && 'text-primary',
                  s.status === 'error' && 'text-destructive'
                )}
              >
                {s.status}
              </span>
            </div>
            {s.input && (
              <pre className="overflow-x-auto whitespace-pre-wrap break-words bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground">
                <span className="font-semibold uppercase tracking-wide">input</span>
                {'\n'}
                {s.input}
              </pre>
            )}
            {s.output && (
              <pre className="overflow-x-auto whitespace-pre-wrap break-words bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground">
                <span className="font-semibold uppercase tracking-wide">output</span>
                {'\n'}
                {s.output}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
