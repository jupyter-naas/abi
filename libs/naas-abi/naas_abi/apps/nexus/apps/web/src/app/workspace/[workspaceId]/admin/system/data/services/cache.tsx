'use client';

import './cache.css';

import { Binary, Braces, Package, ShieldAlert, Type, Zap, type LucideIcon } from 'lucide-react';
import { formatBytes } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, Notice, RelativeTime, type Tone } from '../data-ui';
import { BinaryView } from '../viewers/binary-view';
import { Preview, type PreviewContext } from '../viewers/preview';
import { PrefixBadge, ValueLine } from './keyvalue-parts';
import type { ServiceView } from './types';

const TYPES: Record<string, { label: string; tone: Tone; icon: LucideIcon }> = {
  json: { label: 'JSON', tone: 'info', icon: Braces },
  text: { label: 'Text', tone: 'neutral', icon: Type },
  binary: { label: 'Binary', tone: 'warn', icon: Binary },
  pickle: { label: 'Pickle', tone: 'danger', icon: Package },
};

export function TypeBadge({ type }: { type?: string }) {
  if (!type) return null;
  const known = TYPES[type];
  return <Badge tone={known?.tone ?? 'neutral'}>{known?.label ?? type}</Badge>;
}

function tierTone(tier: string): Tone {
  if (tier === 'hot') return 'warn';
  if (tier === 'cold') return 'info';
  return 'neutral';
}

/** Every tier holding the entry (``tiers`` on an opened entry, else the first one). */
export function TierBadges({ entry }: { entry: ResourceEntry }) {
  const tiers = (entry.attributes.tiers ?? entry.attributes.tier ?? '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
  if (!tiers.length) return null;
  return (
    <span className="data-cache-tiers">
      {tiers.map((tier) => (
        <Badge key={tier} tone={tierTone(tier)}>
          {tier}
        </Badge>
      ))}
    </span>
  );
}

function opaqueLabel(type: string | undefined): string | undefined {
  if (type === 'pickle') return 'Pickled Python object';
  if (type === 'binary') return 'Binary value';
  return undefined;
}

export function CachePreview({ detail, ctx }: { detail: ResourceDetail; ctx: PreviewContext }) {
  const entry = detail.entry;
  const type = entry.attributes.data_type;
  const tiers = entry.attributes.tiers ?? entry.attributes.tier;
  return (
    <div className="data-cache-preview">
      <p className="data-cache-origin">
        <Zap size={13} aria-hidden="true" />
        <span>
          Cached <RelativeTime iso={entry.attributes.created_at} />
        </span>
        {tiers && (
          <>
            <span aria-hidden="true">·</span>
            <span>{tiers.includes(',') ? 'held by' : 'in'}</span>
            <TierBadges entry={entry} />
          </>
        )}
      </p>
      {type === 'pickle' ? (
        <>
          <Notice tone="warn">
            <ShieldAlert size={14} aria-hidden="true" />
            <span>
              A pickled Python object. The System app never loads pickles: unpickling runs code chosen by whoever
              wrote the bytes. Download it, or inspect the raw bytes below.
            </span>
          </Notice>
          <BinaryView name={entry.name} size={entry.size} load={ctx.download} />
        </>
      ) : (
        <Preview detail={detail} ctx={ctx} />
      )}
    </div>
  );
}

export const cacheView: ServiceView = {
  name: 'cache',
  label: 'Cache',
  description: 'Results modules cached, across the hot and cold tiers.',
  icon: Zap,
  group: 'Storage',
  noun: { one: 'entry', many: 'entries' },
  entryIcon: (entry) => TYPES[entry.attributes.data_type ?? '']?.icon ?? Zap,
  badges: (entry) => <PrefixBadge id={entry.id} />,
  summary: (entry) => <ValueLine entry={entry} opaque={opaqueLabel(entry.attributes.data_type)} />,
  level: () => ({
    columns: [
      { id: 'type', label: 'Type', width: '72px', render: (e) => <TypeBadge type={e.attributes.data_type} /> },
      { id: 'tier', label: 'Tier', width: '96px', render: (e) => <TierBadges entry={e} /> },
      {
        id: 'size',
        label: 'Size',
        width: '76px',
        align: 'end',
        render: (e) => <span className="data-num">{formatBytes(e.size)}</span>,
      },
      { id: 'age', label: 'Cached', width: '104px', render: (e) => <RelativeTime iso={e.attributes.created_at} /> },
    ],
    emptyTitle: 'The cache is empty',
    emptyText: 'Entries appear as modules cache results: model calls, lookups, rendered pages.',
  }),
  facts: (detail) => [
    { label: 'Type', value: <TypeBadge type={detail.entry.attributes.data_type} /> },
    { label: 'Tiers', value: <TierBadges entry={detail.entry} /> },
    { label: 'Size', value: formatBytes(detail.entry.size) },
    { label: 'Cached', value: <RelativeTime iso={detail.entry.attributes.created_at} /> },
  ],
  preview: (detail, ctx) => <CachePreview detail={detail} ctx={ctx} />,
  createLabel: 'New entry',
  editor: {
    language: (_id, entry) => (entry?.attributes.data_type === 'json' ? 'json' : 'plaintext'),
    namePlaceholder: 'lookup:company:acme',
  },
  deleteWarning: () =>
    'Removed from every tier. The next read misses, and whatever produced the value computes it again, or fails if nothing can.',
};
