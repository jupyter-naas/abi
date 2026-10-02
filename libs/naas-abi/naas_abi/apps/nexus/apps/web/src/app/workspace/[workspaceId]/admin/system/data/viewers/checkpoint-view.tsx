'use client';

/**
 * A LangGraph checkpoint: a thread's state after one step. The conversation as a
 * transcript (tool calls, results, models, tokens), the other state, the step's
 * pending writes and its metadata. Decoded by the API without importing anything.
 */
import { useState } from 'react';
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronRight,
  Inbox,
  MessageSquare,
  Settings2,
  User,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import { absoluteTime, formatCount } from '../data-model';
import type { CheckpointMessage, CheckpointView as Checkpoint, CheckpointWrite } from '../data-types';
import { Badge, CopyButton, EmptyState, RelativeTime, type Tone } from '../data-ui';
import { JsonTree } from './json-tree';

const ROLES: Record<string, { label: string; icon: LucideIcon }> = {
  human: { label: 'User', icon: User },
  ai: { label: 'Assistant', icon: Bot },
  tool: { label: 'Tool', icon: Wrench },
  system: { label: 'System', icon: Settings2 },
};

const SOURCES: Record<string, { tone: Tone; hint: string }> = {
  input: { tone: 'info', hint: 'Saved when the input arrived, before any step ran' },
  loop: { tone: 'neutral', hint: 'Saved after a step of the graph' },
  update: { tone: 'warn', hint: 'Saved by a manual state update' },
  fork: { tone: 'warn', hint: 'Copied from another checkpoint' },
};

// Characters shown before "Show all"; system prompts are folded shorter.
const CLAMP = 700;
const CLAMP_SYSTEM = 220;

export function brief(value: unknown, limit = 90): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value) ?? '';
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

function Text({ text, clamp }: { text: string; clamp: number }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  const long = text.length > clamp;
  return (
    <div className="ckpt-text">
      <p className="ckpt-text-body">{open || !long ? text : `${text.slice(0, clamp)}…`}</p>
      {long && (
        <button type="button" className="data-text-button" onClick={() => setOpen(!open)}>
          {open ? 'Show less' : `Show all ${formatCount(text.length)} characters`}
        </button>
      )}
    </div>
  );
}

function ToolCall({ call }: { call: NonNullable<CheckpointMessage['tool_calls']>[number] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="ckpt-call">
      <button type="button" className="ckpt-call-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={12} aria-hidden="true" /> : <ChevronRight size={12} aria-hidden="true" />}
        <Wrench size={12} aria-hidden="true" />
        <span className="ckpt-call-name">{call.name ?? 'tool'}</span>
        <span className="ckpt-call-args data-mono">{brief(call.args)}</span>
      </button>
      {open && (
        <div className="ckpt-call-body">
          {call.id && <p className="ckpt-note data-mono">{call.id}</p>}
          <JsonTree value={call.args} toolbar={false} />
        </div>
      )}
    </div>
  );
}

function Message({ message }: { message: CheckpointMessage }) {
  const role = ROLES[message.role] ?? { label: message.role, icon: MessageSquare };
  const Icon = role.icon;
  const usage = message.usage;
  return (
    <li className={`ckpt-message ckpt-message-${message.role}`}>
      <div className="ckpt-message-head">
        <Icon size={13} aria-hidden="true" />
        <span className="ckpt-message-role">
          {message.role === 'tool' && message.name ? `Tool · ${message.name}` : role.label}
        </span>
        {message.model && <Badge mono>{message.model}</Badge>}
        {message.status === 'error' && <Badge tone="danger">error</Badge>}
        <span className="data-spacer" />
        {usage && (usage.input_tokens !== undefined || usage.output_tokens !== undefined) && (
          <span className="ckpt-usage" title="Tokens in → out">
            {formatCount(usage.input_tokens ?? 0)} → {formatCount(usage.output_tokens ?? 0)} tokens
          </span>
        )}
      </div>
      <Text text={message.content} clamp={message.role === 'system' ? CLAMP_SYSTEM : CLAMP} />
      {message.truncated !== undefined && (
        <p className="ckpt-note">Cut at 20,000 of {formatCount(message.truncated)} characters.</p>
      )}
      {message.tool_calls?.map((call, i) => <ToolCall key={call.id ?? i} call={call} />)}
    </li>
  );
}

function isMessage(value: unknown): value is CheckpointMessage {
  return !!value && typeof value === 'object' && 'role' in value && 'content' in value;
}

function Write({ write }: { write: CheckpointWrite }) {
  const value = write.value;
  const messages = Array.isArray(value) && value.every(isMessage) ? (value as CheckpointMessage[]) : isMessage(value) ? [value] : null;
  return (
    <li className="ckpt-write">
      <div className="ckpt-write-head">
        <Badge mono>{write.channel ?? '—'}</Badge>
        <span className="ckpt-write-task data-mono" title={write.task_id ?? undefined}>
          {write.task_path || write.task_id}
        </span>
      </div>
      {messages ? (
        <ol className="ckpt-messages ckpt-messages-nested">
          {messages.map((m, i) => (
            <Message key={m.id ?? i} message={m} />
          ))}
        </ol>
      ) : value === null || value === undefined ? (
        <p className="ckpt-note">No value (a signal for the next step).</p>
      ) : (
        <JsonTree value={value} depth={1} toolbar={false} />
      )}
    </li>
  );
}

type Tab = 'conversation' | 'state' | 'writes' | 'metadata';

export function CheckpointView({ view, onOpen }: { view: Checkpoint; onOpen?: (id: string) => void }) {
  const [tab, setTab] = useState<Tab>('conversation');
  const messages = view.messages ?? [];
  const channels = view.channels ?? {};
  const writes = view.writes ?? [];
  const tokens = messages.reduce((n, m) => n + (m.usage?.total_tokens ?? 0), 0);
  const source = view.source ? SOURCES[view.source] : undefined;
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'conversation', label: 'Conversation', count: messages.length },
    { id: 'state', label: 'State', count: Object.keys(channels).length },
    { id: 'writes', label: 'Pending writes', count: writes.length },
    { id: 'metadata', label: 'Metadata' },
  ];
  return (
    <div className="ckpt">
      <dl className="ckpt-facts">
        <div>
          <dt>Step</dt>
          <dd>
            {view.step ?? '—'}
            {view.source && (
              <Badge tone={source?.tone ?? 'neutral'} title={source?.hint}>
                {view.source}
              </Badge>
            )}
          </dd>
        </div>
        <div>
          <dt>Saved</dt>
          <dd title={view.created_at ? absoluteTime(view.created_at) : undefined}>
            <RelativeTime iso={view.created_at} />
          </dd>
        </div>
        <div>
          <dt>Messages</dt>
          <dd>{formatCount(messages.length)}</dd>
        </div>
        {tokens > 0 && (
          <div>
            <dt>Tokens</dt>
            <dd>{formatCount(tokens)}</dd>
          </div>
        )}
      </dl>
      <dl className="ckpt-ids">
        <div>
          <dt>Agent</dt>
          <dd>
            <code className="data-mono">{view.agent_id ?? '—'}</code>
          </dd>
        </div>
        <div>
          <dt>Thread</dt>
          <dd>
            <code className="data-mono ckpt-id" title={view.thread_id ?? undefined}>
              {view.thread_id ?? '—'}
            </code>
            {view.thread_id && <CopyButton value={view.thread_id} label="Copy thread id" />}
          </dd>
        </div>
        {view.checkpoint_ns && (
          <div>
            <dt>Namespace</dt>
            <dd>
              <code className="data-mono">{view.checkpoint_ns}</code>
            </dd>
          </div>
        )}
        <div>
          <dt>Checkpoint</dt>
          <dd>
            <code className="data-mono ckpt-id">{view.checkpoint_id ?? '—'}</code>
            {view.checkpoint_id && <CopyButton value={view.checkpoint_id} label="Copy checkpoint id" />}
          </dd>
        </div>
        <div>
          <dt>Previous</dt>
          <dd>
            {view.parent_entry && onOpen ? (
              <button type="button" className="data-link ckpt-previous" onClick={() => onOpen(view.parent_entry as string)}>
                <ArrowLeft size={12} aria-hidden="true" /> The step before
              </button>
            ) : view.parent_id ? (
              <code className="data-mono ckpt-id">{view.parent_id}</code>
            ) : (
              <span className="data-muted">First step of the thread</span>
            )}
          </dd>
        </div>
      </dl>
      <div className="data-segmented ckpt-tabs" role="tablist" aria-label="Checkpoint views">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'data-segment data-segment-active' : 'data-segment'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.count ? <span className="ckpt-tab-count">{t.count}</span> : null}
          </button>
        ))}
      </div>
      {tab === 'conversation' &&
        (messages.length ? (
          <ol className="ckpt-messages">
            {messages.map((m, i) => (
              <Message key={m.id ?? i} message={m} />
            ))}
          </ol>
        ) : (
          <EmptyState icon={MessageSquare} title="No messages at this step">
            The state has no message list yet; the Input step of a thread is often empty.
          </EmptyState>
        ))}
      {tab === 'state' &&
        (Object.keys(channels).length ? (
          <JsonTree value={channels} depth={2} />
        ) : (
          <EmptyState icon={Inbox} title="No other state">
            Everything this agent keeps is in the conversation.
          </EmptyState>
        ))}
      {tab === 'writes' &&
        (writes.length ? (
          <ol className="ckpt-writes">
            {writes.map((w, i) => (
              <Write key={`${w.task_id}-${w.index}-${i}`} write={w} />
            ))}
          </ol>
        ) : (
          <EmptyState icon={Inbox} title="No pending writes">
            Writes are what the next step produced before LangGraph saved the following checkpoint.
          </EmptyState>
        ))}
      {tab === 'metadata' && <JsonTree value={view.metadata ?? {}} depth={2} />}
    </div>
  );
}
