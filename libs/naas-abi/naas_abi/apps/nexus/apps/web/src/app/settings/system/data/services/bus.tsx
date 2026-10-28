'use client';

import './bus.css';

import { Binary, File, FileJson, FileText, Lock, Waypoints, type LucideIcon } from 'lucide-react';
import { absoluteTime, formatBytes, formatCount } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, CopyButton, EmptyState, Hint, Notice, RelativeTime, type Tone } from '../data-ui';
import { BinaryView } from '../viewers/binary-view';
import { TextPreview, type PreviewContext } from '../viewers/preview';
import type { ServiceView } from './types';

const KINDS: Record<string, { label: string; tone: Tone }> = {
  kv: { label: 'KV bucket', tone: 'warn' },
  jobs: { label: 'Jobs', tone: 'info' },
  bus: { label: 'Bus', tone: 'accent' },
  other: { label: 'Stream', tone: 'neutral' },
};

const KV_READ_ONLY =
  'This stream backs a key-value bucket. Removing a revision behind the bucket would corrupt its history, so its messages are read-only here. Change entries through the service that owns the bucket.';

const PAYLOAD_ICONS: Record<string, LucideIcon> = { json: FileJson, text: FileText, binary: Binary, empty: File };

export function isKvStream(id: string): boolean {
  return id.split('/')[0].startsWith('KV_');
}

export function KindBadge({ kind }: { kind: string | undefined }) {
  const k = KINDS[kind ?? 'other'] ?? KINDS.other;
  return <Badge tone={k.tone}>{k.label}</Badge>;
}

function Subjects({ value }: { value: string | undefined }) {
  const subjects = (value ?? '').split(', ').filter(Boolean);
  if (!subjects.length) return <span className="data-muted">No subjects</span>;
  return (
    <span className="data-bus-subjects">
      {subjects.slice(0, 4).map((s) => (
        <code key={s} className="data-bus-subject">
          {s}
        </code>
      ))}
      {subjects.length > 4 && <span className="data-muted">+{subjects.length - 4}</span>}
    </span>
  );
}

function streamBadges(entry: ResourceEntry) {
  return (
    <>
      <KindBadge kind={entry.attributes.kind} />
      {(entry.attributes.read_only || isKvStream(entry.id)) && (
        <Hint label={KV_READ_ONLY}>
          <span className="data-bus-lock" aria-label="Read-only">
            <Lock size={11} aria-hidden="true" /> read-only
          </span>
        </Hint>
      )}
    </>
  );
}

function headersOf(detail: ResourceDetail): Record<string, string> {
  const view = detail.view as { type?: string; headers?: Record<string, string> } | null | undefined;
  if (view?.type === 'message' && view.headers) return view.headers;
  return Object.fromEntries(
    Object.entries(detail.entry.attributes)
      .filter(([k]) => k.startsWith('header:'))
      .map(([k, v]) => [k.slice('header:'.length), v]),
  );
}

export function MessagePreview({ detail, ctx }: { detail: ResourceDetail; ctx: PreviewContext }) {
  const view = (detail.view ?? {}) as { subject?: string; sequence?: number; published_at?: string };
  const subject = view.subject ?? detail.entry.attributes.subject ?? detail.entry.name;
  const seq = view.sequence ?? Number(detail.entry.attributes.seq);
  const published = view.published_at ?? detail.entry.modified;
  const headers = Object.entries(headersOf(detail));
  const content = detail.content;
  return (
    <div className="data-bus-preview">
      {isKvStream(detail.entry.id) && <Notice tone="warn">{KV_READ_ONLY}</Notice>}
      <div className="data-bus-envelope">
        <div className="data-bus-envelope-subject">
          <code className="data-mono">{subject}</code>
          <CopyButton value={subject} label="Copy subject" />
        </div>
        <dl className="data-bus-envelope-facts">
          <div>
            <dt>Sequence</dt>
            <dd className="data-mono">{Number.isFinite(seq) ? formatCount(seq) : '—'}</dd>
          </div>
          <div>
            <dt>Published</dt>
            <dd title={absoluteTime(published)}>
              <RelativeTime iso={published} />
            </dd>
          </div>
          <div>
            <dt>Size</dt>
            <dd>{formatBytes(detail.entry.size)}</dd>
          </div>
          <div>
            <dt>Stream</dt>
            <dd className="data-mono">{detail.entry.id.split('/')[0]}</dd>
          </div>
        </dl>
      </div>
      <section className="data-section">
        <h4 className="data-section-title">Payload</h4>
        {!content || (content.encoding === 'text' && !content.text) ? (
          <EmptyState icon={File} title="Empty payload">
            This message carries headers only.
          </EmptyState>
        ) : content.encoding === 'binary' ? (
          <BinaryView name={subject} size={content.size} load={ctx.download} />
        ) : (
          <TextPreview text={content.text ?? ''} name={subject} />
        )}
        {content?.truncated && (
          <p className="data-muted">
            First {formatBytes((content.text ?? '').length)} of {formatBytes(content.size)} shown. Download for the rest.
          </p>
        )}
      </section>
      <section className="data-section">
        <h4 className="data-section-title">Headers{headers.length ? ` · ${headers.length}` : ''}</h4>
        {headers.length ? (
          <table className="data-kv">
            <tbody>
              {headers.map(([k, v]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td className={v === '[REDACTED]' ? 'data-mono data-bus-redacted' : 'data-mono'}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="data-muted">No headers.</p>
        )}
      </section>
    </div>
  );
}

export const busView: ServiceView = {
  name: 'bus',
  label: 'Bus',
  description: 'JetStream streams on the NATS network (bus topics, jobs, key-value buckets) and their stored messages.',
  icon: Waypoints,
  group: 'Streams & logs',
  noun: { one: 'message', many: 'messages' },
  nounFor: (entry) =>
    entry.kind === 'container' ? { one: 'stream', many: 'streams' } : { one: 'message', many: 'messages' },
  entryIcon: (entry) =>
    entry.kind === 'container' ? Waypoints : (PAYLOAD_ICONS[entry.attributes.payload ?? ''] ?? FileText),
  badges: (entry) => {
    if (entry.kind === 'container') return streamBadges(entry);
    return isKvStream(entry.id) ? (
      <span className="data-bus-lock" aria-label="Read-only">
        <Lock size={11} aria-hidden="true" />
      </span>
    ) : null;
  },
  summary: (entry) =>
    entry.kind === 'container' ? (
      <Subjects value={entry.attributes.subjects} />
    ) : entry.attributes.summary ? (
      <span className="data-bus-summary">{entry.attributes.summary}</span>
    ) : null,
  level: (depth, parent) =>
    depth === 0
      ? {
          noun: { one: 'stream', many: 'streams' },
          layout: 'cards',
          card: (e) => <Subjects value={e.attributes.subjects} />,
          columns: [
            {
              id: 'messages',
              label: 'Messages',
              width: '1fr',
              render: (e) => <span className="data-num">{formatCount(Number(e.attributes.messages ?? 0))}</span>,
            },
            { id: 'size', label: 'Size', width: '1fr', render: (e) => <span className="data-num">{formatBytes(e.size)}</span> },
            {
              id: 'consumers',
              label: 'Consumers',
              width: '1fr',
              render: (e) => <span className="data-num">{formatCount(Number(e.attributes.consumers ?? 0))}</span>,
            },
            {
              id: 'last',
              label: 'Last message',
              width: '1fr',
              render: (e) => (e.modified ? <RelativeTime iso={e.modified} /> : <span className="data-muted">—</span>),
            },
          ],
          emptyTitle: 'No JetStream streams',
          emptyText:
            'Streams appear when the bus, jobs or a key-value bucket first publish. If NATS runs without JetStream, enable it (-js) to persist messages.',
        }
      : {
          noun: { one: 'message', many: 'messages' },
          columns: [
            { id: 'seq', label: 'Seq', width: '72px', align: 'end', render: (e) => <span className="data-num">#{e.attributes.seq}</span> },
            { id: 'size', label: 'Size', width: '64px', align: 'end', render: (e) => <span className="data-num">{formatBytes(e.size)}</span> },
            { id: 'published', label: 'Published', width: '96px', render: (e) => <RelativeTime iso={e.modified} /> },
          ],
          notice: isKvStream(parent) ? <Notice tone="warn">{KV_READ_ONLY}</Notice> : undefined,
          emptyTitle: isKvStream(parent) ? 'No revisions stored' : 'No messages stored',
          emptyText: isKvStream(parent)
            ? KV_READ_ONLY
            : 'The stream holds no messages: consumers acknowledged them, limits removed them, or nothing was published yet.',
        },
  facts: (detail) =>
    detail.entry.kind === 'container'
      ? []
      : [
          { label: 'Seq', value: <span className="data-mono">#{detail.entry.attributes.seq}</span> },
          { label: 'Size', value: formatBytes(detail.entry.size) },
          { label: 'Payload', value: detail.entry.attributes.payload ?? '—' },
          { label: 'Published', value: <RelativeTime iso={detail.entry.modified} /> },
        ],
  preview: (detail, ctx) => (detail.entry.kind === 'item' ? <MessagePreview detail={detail} ctx={ctx} /> : null),
  deleteWarning: (entry) => {
    const [stream] = entry.id.split('/');
    const seq = entry.attributes.seq ?? entry.id.split('/').pop();
    return `Removes message #${seq} from ${stream}. Consumers that have not read it yet never will, and it cannot be restored.`;
  },
};
