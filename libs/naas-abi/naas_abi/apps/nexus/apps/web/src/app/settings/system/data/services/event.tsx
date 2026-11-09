'use client';

import './event.css';

import type { ReactNode } from 'react';
import {
  BarChart3,
  Bot,
  Boxes,
  Braces,
  Building2,
  HardDrive,
  KeyRound,
  Lock,
  Mail,
  Network,
  Radio,
  Waypoints,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { absoluteTime, compactIri, dayLabel, formatBytes, formatCount, parseJson, tail } from '../data-model';
import type { ResourceDetail } from '../data-types';
import { Badge, CopyButton, EmptyState, RelativeTime } from '../data-ui';
import { JsonTree } from '../viewers/json-tree';
import type { ServiceView } from './types';

const DOMAIN_ICONS: Record<string, LucideIcon> = {
  agent: Bot,
  analytics: BarChart3,
  bus: Waypoints,
  cache: Zap,
  document: Braces,
  email: Mail,
  keyvalue: KeyRound,
  nexus: Building2,
  object_storage: HardDrive,
  secret: Lock,
  triple_store: Network,
  vector_store: Boxes,
};

export function domainIcon(domain: string | undefined): LucideIcon {
  return DOMAIN_ICONS[domain ?? ''] ?? Radio;
}

/** ``AgentAIMessageEmitted`` → ``Agent AI message emitted`` (the API names types this way too). */
export function humanize(local: string): string {
  const words = local.match(/[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|[A-Z]+|\d+/g);
  if (!words) return local;
  const shown = words.map((w) => (w.length > 1 && w === w.toUpperCase() ? w : w.toLowerCase()));
  shown[0] = shown[0].charAt(0).toUpperCase() + shown[0].slice(1);
  return shown.join(' ');
}

/** ``key=value · key=value`` summaries rendered as facets: keys quiet, values legible. */
export function Facets({ text }: { text: string }) {
  const parts = text.split(' · ').filter(Boolean);
  return (
    <span className="data-event-facets">
      {parts.map((part, i) => {
        const at = part.indexOf('=');
        if (at <= 0) {
          return (
            <span key={i} className="data-event-facet">
              {part}
            </span>
          );
        }
        return (
          <span key={i} className="data-event-facet">
            <span className="data-event-facet-key">{part.slice(0, at)}</span>
            <span className="data-event-facet-value">{part.slice(at + 1)}</span>
          </span>
        );
      })}
    </span>
  );
}

/** ``14:59:40``: the second line of a log time (the first says how long ago). */
export function clock(iso: string): string {
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return '';
  return new Date(at).toLocaleTimeString('en-GB', { hour12: false });
}

/** Relative time over the clock time, the full date on hover: logs are read both ways. */
export function LogTime({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="data-muted">—</span>;
  return (
    <span className="data-event-time" title={absoluteTime(iso)}>
      <RelativeTime iso={iso} />
      <span className="data-event-time-exact">{clock(iso)}</span>
    </span>
  );
}

function Actor({ value }: { value: string | undefined }) {
  if (!value) return <span className="data-muted">—</span>;
  return (
    <span className="data-event-actor" title={value}>
      {value}
    </span>
  );
}

// Plumbing every event carries; the Payload section below still shows all of it.
const BOILERPLATE = new Set(['_uri', '_class_uri', '_property_uris', 'label', 'created', 'creator', 'created_at']);
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

function FieldValue({ value }: { value: unknown }): ReactNode {
  if (typeof value === 'string') {
    if (ISO.test(value)) {
      return (
        <span className="data-event-field-time">
          <RelativeTime iso={value} /> <span className="data-muted">{absoluteTime(value)}</span>
        </span>
      );
    }
    if (/^https?:\/\//.test(value)) {
      return (
        <span className="data-event-field-iri">
          <span className="data-event-iri" title={value}>
            {compactIri(value)}
          </span>
          <CopyButton value={value} label="Copy IRI" />
        </span>
      );
    }
    const embedded = parseJson(value);
    if (embedded !== undefined) return <JsonTree value={embedded} toolbar={false} depth={2} />;
    return <span className="data-event-field-text">{value}</span>;
  }
  if (typeof value === 'number') return <span className="data-num">{formatCount(value)}</span>;
  if (typeof value === 'boolean') return <Badge>{String(value)}</Badge>;
  if (Array.isArray(value) && value.every((v) => typeof v === 'string')) {
    return (
      <span className="data-event-chips">
        {(value as string[]).map((v) => (
          <span key={v} className="data-event-chip" title={v}>
            {/^https?:\/\//.test(v) ? tail(v) : v}
          </span>
        ))}
      </span>
    );
  }
  return <JsonTree value={value} toolbar={false} depth={1} />;
}

function payloadOf(detail: ResourceDetail): unknown {
  const view = detail.view as { type?: string; value?: unknown } | null | undefined;
  if (view?.type === 'json') return view.value;
  return (parseJson(detail.content?.text) as { payload?: unknown } | undefined)?.payload;
}

export function EventPreview({ detail }: { detail: ResourceDetail }) {
  const payload = payloadOf(detail);
  if (payload === undefined) return <EmptyState icon={Radio} title="No payload" />;
  const fields =
    payload && typeof payload === 'object' && !Array.isArray(payload)
      ? Object.entries(payload as Record<string, unknown>).filter(
          ([key, value]) => !BOILERPLATE.has(key) && value !== null && value !== '',
        )
      : [];
  return (
    <div className="data-event-preview">
      {fields.length > 0 && (
        <section className="data-section data-event-fields-section">
          <h4 className="data-section-title">Fields</h4>
          <dl className="data-event-fields">
            {fields.map(([key, value]) => (
              <div key={key} className="data-event-field">
                <dt>{key.replace(/_/g, ' ')}</dt>
                <dd>
                  <FieldValue value={value} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <section className="data-section">
        <h4 className="data-section-title">Payload</h4>
        <JsonTree value={payload} depth={1} />
      </section>
    </div>
  );
}

export const eventView: ServiceView = {
  name: 'event',
  label: 'Events',
  description:
    "The engine's append-only event log: every key set, object written, graph changed and agent run, by event type.",
  icon: Radio,
  group: 'Streams & logs',
  readOnly: true,
  noun: { one: 'event', many: 'events' },
  nounFor: (entry) =>
    entry.kind === 'container' ? { one: 'event type', many: 'event types' } : { one: 'event', many: 'events' },
  entryIcon: (entry) => domainIcon(entry.attributes.domain),
  badges: (entry) => (entry.kind === 'item' && entry.attributes.via ? <Badge>{entry.attributes.via}</Badge> : null),
  summary: (entry) =>
    entry.kind === 'item' && entry.attributes.summary ? (
      <Facets text={entry.attributes.summary} />
    ) : (
      entry.attributes.summary
    ),
  level: (depth) =>
    depth === 0
      ? {
          noun: { one: 'event type', many: 'event types' },
          columns: [
            {
              id: 'domain',
              label: 'Domain',
              width: '112px',
              render: (e) => (e.attributes.domain ? <Badge mono>{e.attributes.domain}</Badge> : null),
            },
            {
              id: 'count',
              label: 'Events',
              width: '72px',
              align: 'end',
              render: (e) => <span className="data-num">{formatCount(Number(e.attributes.count ?? 0))}</span>,
            },
            { id: 'last', label: 'Last seen', width: '96px', render: (e) => <RelativeTime iso={e.modified} /> },
          ],
          emptyTitle: 'No events recorded yet',
          emptyText:
            'Services publish here as they work: keys set, objects written, graphs changed, agents run. Nothing has been published on this engine yet.',
        }
      : {
          noun: { one: 'event', many: 'events' },
          columns: [
            { id: 'when', label: 'When', width: '96px', render: (e) => <LogTime iso={e.modified} /> },
            { id: 'actor', label: 'Actor', width: 'minmax(0, 128px)', render: (e) => <Actor value={e.attributes.actor} /> },
            {
              id: 'size',
              label: 'Size',
              width: '64px',
              align: 'end',
              render: (e) => <span className="data-num">{formatBytes(e.size)}</span>,
            },
          ],
          groupBy: (e) => dayLabel(e.modified),
          emptyTitle: 'No event of this type matches',
          emptyText: 'Search looks inside the payloads; clear it to see every event of this type, newest first.',
        },
  facts: (detail) => {
    const e = detail.entry;
    if (e.kind === 'container') return [];
    return [
      ...(e.attributes.type ? [{ label: 'Type', value: humanize(tail(e.attributes.type)) }] : []),
      { label: 'Seq', value: <span className="data-mono">{e.attributes.seq ?? e.name}</span> },
      { label: 'At', value: <RelativeTime iso={e.modified} /> },
      ...(e.attributes.actor ? [{ label: 'Actor', value: <Actor value={e.attributes.actor} /> }] : []),
    ];
  },
  preview: (detail) => (detail.entry.kind === 'item' ? <EventPreview detail={detail} /> : null),
};
