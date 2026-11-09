'use client';

import './activity-log.css';

import { ArrowLeftRight, CircleUser, Cpu, Globe, ScrollText, UserRound, type LucideIcon } from 'lucide-react';
import { dayLabel, parseJson } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, CopyButton, EmptyState, Notice, RelativeTime, type Tone } from '../data-ui';
import { JsonTree } from '../viewers/json-tree';
import { LogTime } from './event';
import type { ServiceView } from './types';

const KIND_ICONS: Record<string, LucideIcon> = {
  user: UserRound,
  service: Cpu,
  anonymous: Globe,
};

const KIND_TONES: Record<string, Tone> = { user: 'accent', service: 'info', anonymous: 'neutral' };

const SLOW_MS = 1000;

export function MethodPill({ method }: { method: string | undefined }) {
  if (!method) return null;
  const m = method.toUpperCase();
  return <span className={`data-activity-log-method data-activity-log-method-${m.toLowerCase()}`}>{m}</span>;
}

export function statusClass(status: string | number | undefined): string {
  const code = Number(status);
  if (!code) return 'unknown';
  if (code >= 500) return '5xx';
  if (code >= 400) return '4xx';
  if (code >= 300) return '3xx';
  return '2xx';
}

export function StatusCode({ status }: { status: string | number | undefined }) {
  if (status === undefined || status === '') return null;
  return <span className={`data-activity-log-status data-activity-log-status-${statusClass(status)}`}>{status}</span>;
}

function Duration({ ms }: { ms: string | number | undefined }) {
  if (ms === undefined || ms === '') return <span className="data-muted">—</span>;
  const value = Number(ms);
  const shown = value >= SLOW_MS ? `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)} s` : `${value} ms`;
  return <span className={value >= SLOW_MS ? 'data-num data-activity-log-slow' : 'data-num'}>{shown}</span>;
}

interface ActivityDocument {
  actor_id?: string;
  seq?: number;
  event_type?: string;
  timestamp?: string;
  correlation_id?: string | null;
  attributes?: Record<string, unknown>;
}

function documentOf(detail: ResourceDetail): ActivityDocument | undefined {
  const view = detail.view as { type?: string; value?: unknown } | null | undefined;
  if (view?.type === 'json' && view.value && typeof view.value === 'object') return view.value as ActivityDocument;
  return parseJson(detail.content?.text) as ActivityDocument | undefined;
}

const SHOWN = new Set([
  'method',
  'path',
  'status_code',
  'duration_ms',
  'ip',
  'user_agent',
  'query_params',
  'request_body',
  'request_body_size',
  'request_body_truncated',
  'has_auth_header',
  'content_type',
  'error',
]);

/** "[PATH_SKIPPED]" or "[MULTIPART:1234]": why the middleware kept no body. */
function skippedBody(body: unknown): string | null {
  if (typeof body !== 'string') return null;
  const match = body.match(/^\[([A-Z_]+)(?::(\d+))?\]$/);
  if (!match) return null;
  const why: Record<string, string> = {
    PATH_SKIPPED: 'not recorded for this path (it can carry secrets or raw values)',
    MULTIPART: 'not recorded (multipart upload)',
    DISABLED: 'body capture is disabled',
  };
  const size = match[2] ? ` · ${match[2]} bytes` : '';
  return `${why[match[1]] ?? match[1].toLowerCase().replace(/_/g, ' ')}${size}`;
}

export function RequestPreview({ detail }: { detail: ResourceDetail }) {
  const doc = documentOf(detail);
  if (!doc) return <EmptyState icon={ScrollText} title="Nothing recorded" />;
  const a = doc.attributes ?? {};
  if (!a.method && !a.path) {
    return (
      <div className="data-activity-log-preview">
        <p className="data-activity-log-type">{doc.event_type}</p>
        <JsonTree value={a} />
      </div>
    );
  }
  const query = a.query_params && typeof a.query_params === 'object' ? (a.query_params as Record<string, string>) : null;
  const queryString = query ? `?${new URLSearchParams(query).toString()}` : '';
  const skipped = skippedBody(a.request_body);
  const rest = Object.fromEntries(Object.entries(a).filter(([k]) => !SHOWN.has(k)));
  return (
    <div className="data-activity-log-preview">
      <div className="data-activity-log-request">
        <div className="data-activity-log-request-line">
          <MethodPill method={String(a.method ?? '')} />
          <code className="data-activity-log-path">
            {String(a.path ?? '')}
            <span className="data-activity-log-query">{queryString}</span>
          </code>
          <CopyButton value={`${a.path ?? ''}${queryString}`} label="Copy path" />
        </div>
        <dl className="data-activity-log-stats">
          <div>
            <dt>Status</dt>
            <dd>
              <StatusCode status={a.status_code as number | undefined} />
            </dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>
              <Duration ms={a.duration_ms as number | undefined} />
            </dd>
          </div>
          <div>
            <dt>At</dt>
            <dd>
              <RelativeTime iso={doc.timestamp} />
            </dd>
          </div>
          <div>
            <dt>Client</dt>
            <dd className="data-mono">{String(a.ip ?? '—')}</dd>
          </div>
          <div>
            <dt>Signed in</dt>
            <dd>{a.has_auth_header ? <Badge tone="success">yes</Badge> : <Badge>no</Badge>}</dd>
          </div>
        </dl>
        {typeof a.error === 'string' && <Notice tone="danger">Raised {a.error}</Notice>}
        {a.user_agent ? <p className="data-activity-log-agent">{String(a.user_agent)}</p> : null}
        {doc.correlation_id && (
          <p className="data-activity-log-correlation">
            <span className="data-muted">Correlation</span>
            <code className="data-mono">{doc.correlation_id}</code>
            <CopyButton value={doc.correlation_id} label="Copy correlation id" />
          </p>
        )}
      </div>
      {query && (
        <section className="data-section">
          <h4 className="data-section-title">Query parameters</h4>
          <table className="data-kv">
            <tbody>
              {Object.entries(query).map(([k, v]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td className="data-mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {a.request_body !== undefined && (
        <section className="data-section">
          <h4 className="data-section-title">
            Request body
            {typeof a.content_type === 'string' && <span className="data-activity-log-ctype">{a.content_type}</span>}
          </h4>
          {skipped ? (
            <Notice>Body {skipped}.</Notice>
          ) : typeof a.request_body === 'string' ? (
            <pre className="data-text">{a.request_body}</pre>
          ) : (
            <JsonTree value={a.request_body} />
          )}
          {a.request_body_truncated ? <p className="data-muted">Truncated when recorded.</p> : null}
        </section>
      )}
      {Object.keys(rest).length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Other attributes</h4>
          <JsonTree value={rest} />
        </section>
      )}
    </div>
  );
}

function actorIcon(entry: ResourceEntry): LucideIcon {
  if (entry.kind === 'item') return entry.attributes.method ? ArrowLeftRight : ScrollText;
  return KIND_ICONS[entry.attributes.kind ?? ''] ?? CircleUser;
}

export const activityLogView: ServiceView = {
  name: 'activity_log',
  label: 'Activity log',
  description: 'Every API request and recorded action, per actor: who called what, how it answered, how long it took.',
  icon: ScrollText,
  group: 'Streams & logs',
  readOnly: true,
  noun: { one: 'event', many: 'events' },
  nounFor: (entry) =>
    entry.kind === 'container' ? { one: 'actor', many: 'actors' } : { one: 'request', many: 'requests' },
  entryIcon: actorIcon,
  level: (depth) =>
    depth === 0
      ? {
          noun: { one: 'actor', many: 'actors' },
          columns: [
            {
              id: 'kind',
              label: 'Kind',
              width: '96px',
              render: (e) =>
                e.attributes.kind ? <Badge tone={KIND_TONES[e.attributes.kind] ?? 'neutral'}>{e.attributes.kind}</Badge> : null,
            },
            { id: 'last', label: 'Last active', width: '104px', render: (e) => <RelativeTime iso={e.modified} /> },
          ],
          emptyTitle: 'No activity yet',
          emptyText: 'Requests to the API are recorded here per actor as soon as anyone signs in or calls it.',
        }
      : {
          noun: { one: 'request', many: 'requests' },
          columns: [
            { id: 'method', label: 'Method', width: '64px', render: (e) => <MethodPill method={e.attributes.method} /> },
            { id: 'status', label: 'Status', width: '48px', render: (e) => <StatusCode status={e.attributes.status} /> },
            {
              id: 'duration',
              label: 'Took',
              width: '64px',
              align: 'end',
              render: (e) => <Duration ms={e.attributes.duration_ms} />,
            },
            { id: 'when', label: 'When', width: '96px', render: (e) => <LogTime iso={e.modified} /> },
          ],
          groupBy: (e) => dayLabel(e.modified),
          emptyTitle: 'No requests recorded',
          emptyText: 'This actor has no recorded activity yet.',
        },
  facts: (detail) => {
    const a = detail.entry.attributes;
    if (detail.entry.kind === 'container') return [];
    return [
      ...(a.method ? [{ label: 'Method', value: <MethodPill method={a.method} /> }] : []),
      ...(a.status ? [{ label: 'Status', value: <StatusCode status={a.status} /> }] : []),
      ...(a.duration_ms ? [{ label: 'Took', value: <Duration ms={a.duration_ms} /> }] : []),
      { label: 'At', value: <RelativeTime iso={detail.entry.modified} /> },
    ];
  },
  preview: (detail) => (detail.entry.kind === 'item' ? <RequestPreview detail={detail} /> : null),
};
