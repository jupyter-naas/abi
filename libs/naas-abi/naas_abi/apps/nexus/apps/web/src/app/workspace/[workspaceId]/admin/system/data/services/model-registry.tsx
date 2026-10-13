'use client';

import './model-registry.css';

import { Cpu, Layers, Sparkles, Star } from 'lucide-react';
import { formatCount, parseJson } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, CopyButton } from '../data-ui';
import { JsonTree } from '../viewers/json-tree';
import type { ServiceView } from './types';

/** 200000 → "200K", 1048576 → "1M". */
export function formatTokens(value: number | string | undefined | null): string {
  const n = Number(value);
  if (!value || Number.isNaN(n) || n <= 0) return '—';
  if (n >= 1_000_000) return `${Number((n / 1_000_000).toFixed(n % 1_000_000 ? 1 : 0))}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return formatCount(n);
}

/** A USD amount per million tokens, short. */
export function formatPrice(value: number | string | undefined | null): string {
  const n = Number(value);
  if (value === undefined || value === null || value === '' || Number.isNaN(n)) return '—';
  if (n === 0) return 'free';
  return `$${n >= 10 ? Number(n.toFixed(2)) : Number(n.toFixed(3))}`;
}

/** An OpenRouter-style per-token price as USD per million tokens. */
export function perMillion(value: unknown): number | null {
  const n = Number(value);
  if (value === undefined || value === null || value === '' || Number.isNaN(n)) return null;
  return n * 1_000_000;
}

function KindBadge({ kind }: { kind: string | undefined }) {
  if (!kind) return null;
  return (
    <>
      {kind.split(',').map((k) => {
        const name = k.trim();
        return (
          <Badge key={name} tone={name === 'embedding' ? 'accent' : 'info'}>
            {name === 'embedding' ? <Layers size={11} aria-hidden="true" /> : <Sparkles size={11} aria-hidden="true" />}
            {name}
          </Badge>
        );
      })}
    </>
  );
}

function DefaultBadges({ value }: { value: string | undefined }) {
  if (!value) return null;
  return (
    <>
      {value.split(',').map((d) => (
        <Badge key={d} tone="warn" title={`The engine's default ${d.trim()} model`}>
          <Star size={11} aria-hidden="true" /> default {d.trim()}
        </Badge>
      ))}
    </>
  );
}

function providers(entry: ResourceEntry): string[] {
  return (entry.attributes.providers ?? '')
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean);
}

function ModelCard({ entry }: { entry: ResourceEntry }) {
  const a = entry.attributes;
  return (
    <div className="data-models-card">
      {a.display_name && a.display_name !== entry.name && <p className="data-models-name">{a.display_name}</p>}
      {a.summary && <p className="data-models-summary">{a.summary}</p>}
      <span className="data-models-providers">
        {providers(entry).map((p) => (
          <Badge key={p} mono>
            {p}
          </Badge>
        ))}
      </span>
    </div>
  );
}

interface SheetModel {
  provider: string;
  model_id: string;
  kind: string;
  name?: string | null;
  description?: string | null;
  context_window?: number | null;
  dimensions?: number | null;
  pricing?: Record<string, unknown> | null;
  top_provider?: Record<string, unknown> | null;
  architecture?: Record<string, unknown> | null;
  supported_parameters?: string[] | null;
}

interface Sheet {
  canonical_id: string;
  default_for: string[];
  models: SheetModel[];
}

function sheetOf(detail: ResourceDetail): Sheet | null {
  const value = detail.view?.type === 'json' ? (detail.view as { value: unknown }).value : parseJson(detail.content?.text);
  if (!value || typeof value !== 'object' || !('models' in (value as object))) return null;
  return value as Sheet;
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="data-models-tile">
      <span className="data-models-tile-label">{label}</span>
      <span className="data-models-tile-value">{value}</span>
      {hint && <span className="data-models-tile-hint">{hint}</span>}
    </div>
  );
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export function ModelSheet({ detail }: { detail: ResourceDetail }) {
  const sheet = sheetOf(detail);
  if (!sheet) return null;
  const a = detail.entry.attributes;
  const first = sheet.models[0];
  const description = sheet.models.find((m) => m.description)?.description;
  const parameters = [...new Set(sheet.models.flatMap((m) => m.supported_parameters ?? []))].sort();
  const inputs = [...new Set(sheet.models.flatMap((m) => strings(m.architecture?.input_modalities)))];
  const outputs = [...new Set(sheet.models.flatMap((m) => strings(m.architecture?.output_modalities)))];
  const embedding = first?.kind === 'embedding';
  return (
    <div className="data-models-sheet">
      <header className="data-models-sheet-head">
        <h3 className="data-models-sheet-title">{a.display_name || sheet.canonical_id}</h3>
        <span className="data-models-sheet-badges">
          <KindBadge kind={a.kind} />
          <DefaultBadges value={a.default} />
        </span>
      </header>
      {description && <p className="data-models-description">{description}</p>}
      <div className="data-models-tiles">
        {embedding ? (
          <Tile label="Dimensions" value={a.dimensions ? formatCount(Number(a.dimensions)) : '—'} />
        ) : (
          <>
            <Tile label="Context" value={formatTokens(a.context_window)} hint="tokens" />
            <Tile label="Max output" value={formatTokens(a.max_output_tokens)} hint="tokens" />
          </>
        )}
        <Tile label="Input" value={formatPrice(a.input_price)} hint="per M tokens" />
        {!embedding && <Tile label="Output" value={formatPrice(a.output_price)} hint="per M tokens" />}
      </div>
      <section className="data-section">
        <h4 className="data-section-title">Providers · {sheet.models.length}</h4>
        <table className="data-kv data-models-providers-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Model id</th>
              <th className="data-align-end">Context</th>
              <th className="data-align-end">In / out per M</th>
            </tr>
          </thead>
          <tbody>
            {sheet.models.map((m) => (
              <tr key={`${m.provider}:${m.model_id}`}>
                <td>
                  <Badge mono>{m.provider}</Badge>
                </td>
                <td>
                  <span className="data-models-id">
                    <code className="data-mono">{m.model_id}</code>
                    <CopyButton value={m.model_id} label="Copy model id" />
                  </span>
                </td>
                <td className="data-align-end data-num">{formatTokens(m.context_window)}</td>
                <td className="data-align-end data-num">
                  {formatPrice(perMillion(m.pricing?.prompt))} / {formatPrice(perMillion(m.pricing?.completion))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {(inputs.length > 0 || outputs.length > 0) && (
        <section className="data-section">
          <h4 className="data-section-title">Modalities</h4>
          <p className="data-models-modalities">
            {inputs.join(', ') || '—'} <span className="data-muted">→</span> {outputs.join(', ') || '—'}
          </p>
        </section>
      )}
      {parameters.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Supported parameters</h4>
          <span className="data-models-chips">
            {parameters.map((p) => (
              <Badge key={p} mono>
                {p}
              </Badge>
            ))}
          </span>
        </section>
      )}
      <section className="data-section">
        <h4 className="data-section-title">Registry entry</h4>
        <JsonTree value={sheet} depth={1} />
      </section>
    </div>
  );
}

export const modelRegistryView: ServiceView = {
  name: 'model_registry',
  label: 'Models',
  description: 'Chat and embedding models registered in this engine, by canonical id, with their providers and limits.',
  icon: Cpu,
  group: 'Platform',
  readOnly: true,
  noun: { one: 'model', many: 'models' },
  entryIcon: (entry) => ((entry.attributes.kind ?? '').includes('embedding') ? Layers : Sparkles),
  level: () => ({
    layout: 'cards',
    card: (entry) => <ModelCard entry={entry} />,
    columns: [
      {
        id: 'context',
        label: 'Context · out',
        width: '1fr',
        render: (e) =>
          e.attributes.dimensions ? (
            <span className="data-num">{e.attributes.dimensions} dims</span>
          ) : (
            <span className="data-num">
              {formatTokens(e.attributes.context_window)}
              {e.attributes.max_output_tokens ? ` · ${formatTokens(e.attributes.max_output_tokens)}` : ''}
            </span>
          ),
      },
      {
        id: 'price',
        label: 'In / out $/M',
        width: '1fr',
        render: (e) => (
          <span className="data-num">
            {e.attributes.input_price || e.attributes.output_price
              ? `${formatPrice(e.attributes.input_price)} / ${formatPrice(e.attributes.output_price)}`
              : '—'}
          </span>
        ),
      },
    ],
    emptyTitle: 'No model registered',
    emptyText: 'Models appear here once modules register them at load (AI provider modules, for example).',
  }),
  badges: (entry) => (
    <>
      <KindBadge kind={entry.attributes.kind} />
      <DefaultBadges value={entry.attributes.default} />
    </>
  ),
  facts: (detail) => [
    { label: 'Providers', value: providers(detail.entry).join(', ') || '—' },
    { label: 'Context', value: formatTokens(detail.entry.attributes.context_window) },
  ],
  preview: (detail) => (sheetOf(detail) ? <ModelSheet detail={detail} /> : null),
};
