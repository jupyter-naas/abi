'use client';

import './keyvalue.css';

import { Binary, Braces, Fingerprint, KeyRound, ListOrdered, Lock, Timer, type LucideIcon } from 'lucide-react';
import { absoluteTime, detectLanguage, formatBytes } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Notice } from '../data-ui';
import { Preview, type PreviewContext } from '../viewers/preview';
import { EncodingBadge, PrefixBadge, TtlBadge, ValueLine, keyFamily, keyPrefix } from './keyvalue-parts';
import type { ServiceView } from './types';

export function keyIcon(entry: ResourceEntry): LucideIcon {
  const family = keyFamily(entry.id);
  if (family === 'lock') return Lock;
  if (family === 'session') return Fingerprint;
  if (family === 'job') return ListOrdered;
  if (entry.attributes.encoding === 'json') return Braces;
  if (entry.attributes.encoding === 'binary') return Binary;
  return KeyRound;
}

const FAMILY_NOTES = {
  lock: 'This key looks like a lock: its value is the holder’s token. Deleting it releases the lock while the holder may still be working.',
  session: 'This key looks like a session or a sign-in token. Deleting it ends that session.',
  job: 'This key looks like job bookkeeping. Changing it can make a job run again or be skipped.',
} as const;

export function KeyValuePreview({ detail, ctx }: { detail: ResourceDetail; ctx: PreviewContext }) {
  const expiresAt = detail.entry.attributes.expires_at;
  const family = keyFamily(detail.entry.id);
  return (
    <div className="data-keyvalue-preview">
      {expiresAt && (
        <Notice tone="info">
          <Timer size={14} aria-hidden="true" />
          <span>
            Expires <TtlBadge expiresAt={expiresAt} /> · {absoluteTime(expiresAt)}
          </span>
        </Notice>
      )}
      {family && family !== 'other' && <Notice tone="warn">{FAMILY_NOTES[family]}</Notice>}
      <Preview detail={detail} ctx={ctx} />
    </div>
  );
}

export function keyDeleteWarning(entry: ResourceEntry): string {
  const family = keyFamily(entry.id);
  if (family === 'lock') {
    return 'Deleting a lock releases it at once: another process can take it while the current holder still believes it owns it.';
  }
  if (family === 'session') {
    return 'Deleting a session key signs that session out; whoever holds it has to authenticate again.';
  }
  if (family === 'job') {
    return 'Jobs reading this key lose their bookkeeping and may run again.';
  }
  return 'Modules reading this key get "not found" afterwards, as if it had expired.';
}

export const keyValueView: ServiceView = {
  name: 'keyvalue',
  label: 'Key-value',
  description: 'Small values, sessions and locks modules keep by key, with optional expiry.',
  icon: KeyRound,
  group: 'Storage',
  noun: { one: 'key', many: 'keys' },
  entryIcon: keyIcon,
  badges: (entry) => <PrefixBadge id={entry.id} />,
  summary: (entry) => <ValueLine entry={entry} opaque={entry.attributes.encoding === 'binary' ? 'Binary value' : undefined} />,
  level: () => ({
    columns: [
      {
        id: 'encoding',
        label: 'Value',
        width: '72px',
        render: (e) => <EncodingBadge encoding={e.attributes.encoding} />,
      },
      {
        id: 'size',
        label: 'Size',
        width: '76px',
        align: 'end',
        render: (e) => <span className="data-num">{formatBytes(e.size)}</span>,
      },
      {
        id: 'expiry',
        label: 'Expiry',
        width: '150px',
        render: (e) => <TtlBadge expiresAt={e.attributes.expires_at} />,
      },
    ],
    emptyTitle: 'No keys',
    emptyText: 'Keys appear when modules store values, open sessions or take locks.',
  }),
  facts: (detail) => {
    const prefix = keyPrefix(detail.entry.id);
    return [
      { label: 'Size', value: formatBytes(detail.entry.size) },
      { label: 'Expiry', value: <TtlBadge expiresAt={detail.entry.attributes.expires_at} /> },
      { label: 'Value', value: <EncodingBadge encoding={detail.entry.attributes.encoding} /> },
      ...(prefix ? [{ label: 'Family', value: <span className="data-mono">{prefix}</span> }] : []),
    ];
  },
  preview: (detail, ctx) => <KeyValuePreview detail={detail} ctx={ctx} />,
  createLabel: 'New key',
  editor: {
    language: (id, entry) => (entry?.attributes.encoding === 'json' ? 'json' : detectLanguage(id)),
    // Short text values edit in a single field; JSON and long values get Monaco.
    compact: (entry) =>
      entry !== undefined && entry.attributes.encoding === 'text' && (entry.size ?? 0) <= 512,
    namePlaceholder: 'feature:flags',
    allowUpload: true,
  },
  deleteWarning: keyDeleteWarning,
};
