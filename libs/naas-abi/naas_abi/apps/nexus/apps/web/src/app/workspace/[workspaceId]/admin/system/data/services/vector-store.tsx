'use client';

import './vector-store.css';

import { Boxes, Quote, ScatterChart } from 'lucide-react';
import { formatCount } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { CopyButton } from '../data-ui';
import { VectorBars, VectorView } from '../viewers/vector-view';
import type { Level, ServiceView } from './types';
import { VECTOR_TEMPLATE, parseSample, textExcerpt, validateVectorDocument } from './vector-store-model';

const EXCERPT_LIMIT = 1200;

function CollectionCard({ entry }: { entry: ResourceEntry }) {
  const sample = parseSample(entry.attributes.sample);
  if (sample.length) {
    return (
      <span className="data-vector-card">
        <span className="data-vector-spark" title="First components of one stored vector">
          <VectorBars components={sample} />
        </span>
      </span>
    );
  }
  // Only claim emptiness when the API says so; otherwise there is just no sample.
  if (entry.attributes.documents !== '0') return null;
  return (
    <span className="data-vector-card">
      <span className="data-vector-spark data-vector-spark-empty">No vectors yet</span>
    </span>
  );
}

function level(depth: number): Level {
  if (depth === 0) {
    return {
      noun: { one: 'collection', many: 'collections' },
      layout: 'cards',
      card: (e) => <CollectionCard entry={e} />,
      columns: [
        {
          id: 'documents',
          label: 'Vectors',
          width: '1fr',
          render: (e) =>
            e.attributes.documents ? (
              <span className="data-num">{formatCount(Number(e.attributes.documents))}</span>
            ) : (
              <span className="data-num">—</span>
            ),
        },
        {
          id: 'dimension',
          label: 'Dimension',
          width: '1fr',
          render: (e) => <span className="data-num">{e.attributes.dimension ?? '—'}</span>,
        },
        { id: 'distance', label: 'Distance', width: '1fr', render: (e) => e.attributes.distance ?? '—' },
      ],
      emptyTitle: 'No vector collections',
      emptyText: 'Collections appear when a module indexes embeddings. Writing a vector to a new collection creates it.',
    };
  }
  return {
    noun: { one: 'vector', many: 'vectors' },
    columns: [
      {
        id: 'fields',
        label: 'Fields',
        width: 'minmax(120px, 0.45fr)',
        render: (e) =>
          e.attributes.fields ? (
            <span className="data-vector-fields" title={e.attributes.fields}>
              {e.attributes.fields}
            </span>
          ) : (
            <span className="data-muted">—</span>
          ),
      },
    ],
    emptyTitle: 'This collection holds no vectors',
    emptyText: 'Add one with its vector, metadata and payload, or let the indexing module write here.',
  };
}

function VectorPreview({ detail }: { detail: ResourceDetail }) {
  const view = detail.view as {
    type: 'vector';
    dimension: number;
    components: number[];
    norm?: number | null;
    metadata?: unknown;
    payload?: unknown;
  };
  const excerpt = textExcerpt(view.payload, view.metadata);
  const clipped = excerpt && excerpt.text.length > EXCERPT_LIMIT;
  return (
    <div className="data-vector-preview">
      {excerpt && (
        <figure className="data-vector-excerpt">
          <figcaption className="data-vector-excerpt-head">
            <Quote size={13} aria-hidden="true" />
            <span>Embeds · {excerpt.field}</span>
            <span className="data-spacer" />
            <CopyButton value={excerpt.text} label="Copy text" />
          </figcaption>
          <blockquote className="data-vector-excerpt-text">
            {clipped ? `${excerpt.text.slice(0, EXCERPT_LIMIT)}…` : excerpt.text}
          </blockquote>
        </figure>
      )}
      <VectorView
        dimension={view.dimension}
        components={view.components}
        norm={view.norm}
        metadata={view.metadata}
        payload={view.payload}
      />
    </div>
  );
}

export const vectorStoreView: ServiceView = {
  name: 'vector_store',
  label: 'Vector store',
  description: 'Embeddings and their payloads, by collection.',
  icon: Boxes,
  group: 'Storage',
  noun: { one: 'vector', many: 'vectors' },
  entryIcon: (e) => (e.kind === 'container' ? Boxes : ScatterChart),
  nounFor: (e) => (e.kind === 'container' ? { one: 'collection', many: 'collections' } : { one: 'vector', many: 'vectors' }),
  level,
  canCreate: (depth) => (depth >= 1 ? true : 'Open a collection to add vectors to it.'),
  facts: (detail) => {
    const view = detail.view as { type?: string; dimension?: number; norm?: number | null } | null | undefined;
    if (view?.type !== 'vector') return [];
    return [
      { label: 'Dimension', value: formatCount(view.dimension ?? 0) },
      { label: 'Norm', value: view.norm === null || view.norm === undefined ? '—' : view.norm.toFixed(3) },
      { label: 'Fields', value: detail.entry.attributes.fields ?? '—' },
    ];
  },
  preview: (detail) => (detail.view?.type === 'vector' ? <VectorPreview detail={detail} /> : null),
  createLabel: 'New vector',
  editor: {
    language: () => 'json',
    template: () => VECTOR_TEMPLATE,
    validate: validateVectorDocument,
    namePlaceholder: 'document-id',
  },
  deleteWarning: (e) => {
    if (e.kind === 'container') {
      const n = Number(e.attributes.documents);
      const what = Number.isFinite(n) ? `its ${formatCount(n)} ${n === 1 ? 'vector' : 'vectors'}` : 'every vector';
      return `Removes the ${e.name} collection with ${what} and their payloads. Searches against it fail until a module recreates and refills it.`;
    }
    return `Removes ${e.name} and its payload. It stops matching similarity searches at once.`;
  },
};
