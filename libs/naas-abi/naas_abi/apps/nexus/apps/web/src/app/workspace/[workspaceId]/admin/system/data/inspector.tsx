'use client';

/** The right pane: one entry, previewed, raw, described, with its history and actions. */
import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Download,
  Eye,
  EyeOff,
  FileText,
  Folder,
  History as HistoryIcon,
  Lock,
  Pencil,
  Trash2,
  X,
} from 'lucide-react';
import type { Failure, Result } from './data-api';
import { absoluteTime, detectLanguage, formatBytes, formatCount } from './data-model';
import type { AuditEntry, ResourceDetail } from './data-types';
import {
  Avatar,
  Badge,
  CopyButton,
  EmptyState,
  Field,
  Hint,
  Notice,
  RelativeTime,
  SkeletonRows,
  StatusPill,
  useNow,
} from './data-ui';
import type { ServiceView } from './services/types';
import { CodeView } from './viewers/code-view';
import { Preview, type PreviewContext } from './viewers/preview';

type Tab = 'preview' | 'raw' | 'details' | 'history';

/** Percent-encoded ids (IRIs inside ids) shown decoded; copies keep the raw id. */
export function readableId(id: string): string {
  if (!/%[0-9A-Fa-f]{2}/.test(id)) return id;
  try {
    return decodeURIComponent(id);
  } catch {
    return id;
  }
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'preview', label: 'Preview' },
  { id: 'raw', label: 'Raw' },
  { id: 'details', label: 'Details' },
  { id: 'history', label: 'History' },
];

const VERBS: Record<string, string> = {
  create: 'created',
  replace: 'replaced',
  delete: 'deleted',
  reveal: 'revealed',
};

/** One line per change: a ``requested`` record merged with its outcome. */
export function groupHistory(entries: AuditEntry[]): (AuditEntry & { outcome: string })[] {
  const out: (AuditEntry & { outcome: string })[] = [];
  const used = new Set<number>();
  entries.forEach((entry, i) => {
    if (used.has(i)) return;
    if (entry.phase === 'requested') {
      out.push({ ...entry, outcome: 'unknown' });
      return;
    }
    const match = entries.findIndex(
      (other, j) =>
        j > i &&
        !used.has(j) &&
        other.phase === 'requested' &&
        other.operation === entry.operation &&
        other.actor_id === entry.actor_id,
    );
    if (match >= 0) used.add(match);
    out.push({ ...entry, outcome: entry.phase });
  });
  return out;
}

function HistoryTab({ load }: { load: () => Promise<Result<{ entries: AuditEntry[] }>> }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  useEffect(() => {
    let cancelled = false;
    void load().then((result) => {
      if (cancelled) return;
      if (result.ok) setEntries(result.data.entries);
      else setFailure(result);
    });
    return () => {
      cancelled = true;
    };
  }, [load]);
  if (failure) return <Notice tone="danger">{failure.reason}</Notice>;
  if (!entries) return <SkeletonRows rows={3} />;
  const grouped = groupHistory(entries);
  if (!grouped.length) {
    return (
      <EmptyState icon={HistoryIcon} title="No changes from the System app">
        Changes and reveals made here are recorded in the audit log and listed here.
      </EmptyState>
    );
  }
  return (
    <ol className="data-history">
      {grouped.map((e, i) => (
        <li key={`${e.at}-${i}`} className="data-history-item">
          <Avatar name={e.actor || e.actor_id} />
          <div className="data-history-body">
            <p className="data-history-line">
              <strong>{e.actor || e.actor_id}</strong> {VERBS[e.operation] ?? e.operation} it
              {e.outcome === 'failed' && <StatusPill tone="danger" label="failed" />}
              {e.outcome === 'unknown' && <StatusPill tone="warn" label="no outcome recorded" />}
            </p>
            <p className="data-history-meta">
              <RelativeTime iso={e.at} />
              {e.error ? ` · ${e.error}` : ''}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RawTab({ detail }: { detail: ResourceDetail }) {
  const content = detail.content;
  if (!content) return <EmptyState icon={FileText} title="No value" />;
  if (content.encoding === 'masked') {
    return <EmptyState icon={Lock} title="Value hidden">Reveal it to see the raw value.</EmptyState>;
  }
  if (content.encoding === 'binary') {
    return (
      <EmptyState icon={FileText} title="Binary content">
        {formatBytes(content.size)}. Download it, or open Preview for a hex dump.
      </EmptyState>
    );
  }
  const language = detectLanguage(detail.entry.name, detail.entry.attributes.media_type, content.text);
  const text =
    language === 'json' && content.text
      ? (() => {
          try {
            return JSON.stringify(JSON.parse(content.text), null, 2);
          } catch {
            return content.text;
          }
        })()
      : (content.text ?? '');
  return (
    <div className="data-raw">
      <CodeView value={text} language={language} />
    </div>
  );
}

function DetailsTab({ detail }: { detail: ResourceDetail }) {
  const e = detail.entry;
  const attributes = Object.entries(e.attributes).filter(([k]) => k !== 'summary');
  return (
    <dl className="data-fields">
      <Field label="Id">
        <span className="data-field-copy">
          <code className="data-mono">{e.id}</code>
          <CopyButton value={e.id} label="Copy id" />
        </span>
      </Field>
      <Field label="Name">{e.name}</Field>
      <Field label="Kind">{e.kind === 'container' ? 'Container' : 'Item'}</Field>
      {e.size !== null && <Field label="Size">{`${formatBytes(e.size)} (${formatCount(e.size)} bytes)`}</Field>}
      {e.modified && <Field label="Modified">{absoluteTime(e.modified)}</Field>}
      {attributes.map(([key, value]) => (
        <Field key={key} label={key.replace(/_/g, ' ')}>
          <span className="data-field-copy">
            <span className="data-mono">{value}</span>
            <CopyButton value={value} label={`Copy ${key}`} />
          </span>
        </Field>
      ))}
      <Field label="Actions">{e.actions.length ? e.actions.join(', ') : 'none'}</Field>
    </dl>
  );
}

function RevealBar({ until, onHide }: { until: number; onHide: () => void }) {
  const now = useNow(250);
  const left = Math.max(0, Math.ceil((until - now) / 1000));
  return (
    <div className="data-reveal-bar" role="status">
      <Eye size={14} aria-hidden="true" />
      <span>
        Visible for <strong>{left} s</strong> · recorded in the audit log
      </span>
      <button type="button" className="data-text-button" onClick={onHide}>
        Hide now
      </button>
    </div>
  );
}

export function Inspector({
  view,
  detail,
  loading,
  failure,
  revealedUntil,
  revealing,
  width,
  onResize,
  onClose,
  onReveal,
  onHide,
  onDownload,
  onEdit,
  onDelete,
  loadHistory,
  previewContext,
}: {
  view: ServiceView;
  detail: ResourceDetail | null;
  loading: boolean;
  failure: Failure | null;
  revealedUntil: number | null;
  revealing: boolean;
  width: number;
  onResize: (width: number) => void;
  onClose: () => void;
  onReveal: () => void;
  onHide: () => void;
  onDownload: () => void;
  onEdit: () => void;
  onDelete: () => void;
  loadHistory: () => Promise<Result<{ entries: AuditEntry[] }>>;
  previewContext: PreviewContext;
}) {
  const [tab, setTab] = useState<Tab>('preview');
  const entryId = detail?.entry.id;
  useEffect(() => setTab('preview'), [entryId]);
  const facts = useMemo(() => {
    if (!detail) return [];
    if (view.facts) return view.facts(detail);
    const out: { label: string; value: React.ReactNode }[] = [];
    if (detail.entry.size !== null) out.push({ label: 'Size', value: formatBytes(detail.entry.size) });
    if (detail.entry.modified) out.push({ label: 'Modified', value: <RelativeTime iso={detail.entry.modified} /> });
    return out;
  }, [detail, view]);

  const startResize = (event: React.PointerEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = width;
    const move = (e: PointerEvent) => onResize(startWidth + (startX - e.clientX));
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const actions = detail?.entry.actions ?? [];
  const readOnly = Boolean(detail) && !actions.some((a) => a === 'write' || a === 'delete');
  const Icon = detail ? (view.entryIcon?.(detail.entry) ?? (detail.entry.kind === 'container' ? Folder : FileText)) : FileText;
  const custom = detail && tab === 'preview' ? view.preview?.(detail, previewContext) : null;

  return (
    <aside className="data-inspector" style={{ width }} aria-label="Selected entry">
      <div
        className="data-inspector-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize"
        tabIndex={0}
        onPointerDown={startResize}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') onResize(width + 24);
          if (e.key === 'ArrowRight') onResize(width - 24);
        }}
      />
      {loading && !detail ? (
        <div className="data-inspector-loading">
          <SkeletonRows rows={4} />
        </div>
      ) : failure && !detail ? (
        <div className="data-inspector-loading">
          <div className="data-inspector-top">
            <span className="data-spacer" />
            <button type="button" className="data-icon-button" aria-label="Close" onClick={onClose}>
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          <EmptyState icon={AlertTriangle} title={failure.status === 404 ? 'Not found' : 'Could not open it'}>
            {failure.reason}
          </EmptyState>
        </div>
      ) : detail ? (
        <>
          <header className="data-inspector-header">
            <div className="data-inspector-top">
              <span className="data-inspector-icon">
                <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div className="data-inspector-heading">
                <h3 className="data-inspector-title" title={detail.entry.name}>
                  {view.title?.(detail.entry) ?? detail.entry.name}
                </h3>
                {detail.entry.id !== detail.entry.name ? (
                  <div className="data-inspector-id">
                    <code className="data-mono" title={detail.entry.id}>
                      {readableId(detail.entry.id)}
                    </code>
                    <CopyButton value={detail.entry.id} label="Copy id" />
                  </div>
                ) : (
                  <div className="data-inspector-id">
                    <span className="data-muted">{view.noun.one.replace(/^\w/, (c) => c.toUpperCase())}</span>
                    <CopyButton value={detail.entry.id} label="Copy name" />
                  </div>
                )}
              </div>
              <Hint label="Close" shortcut="Esc">
                <button type="button" className="data-icon-button" aria-label="Close" onClick={onClose}>
                  <X size={16} aria-hidden="true" />
                </button>
              </Hint>
            </div>
            {(facts.length > 0 || view.badges || readOnly) && (
              <div className="data-inspector-facts">
                {readOnly && <Badge>Read-only</Badge>}
                {view.badges?.(detail.entry)}
                {facts.map((f) => (
                  <span key={f.label} className="data-fact">
                    <span className="data-fact-label">{f.label}</span>
                    <span className="data-fact-value">{f.value}</span>
                  </span>
                ))}
              </div>
            )}
            <nav className="data-inspector-tabs" role="tablist" aria-label="Views">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  className={tab === t.id ? 'data-inspector-tab data-inspector-tab-active' : 'data-inspector-tab'}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </header>
          {revealedUntil !== null && <RevealBar until={revealedUntil} onHide={onHide} />}
          <div className={`data-inspector-body data-inspector-body-${tab}`}>
            {tab === 'preview' && (custom ?? <Preview detail={detail} ctx={previewContext} />)}
            {tab === 'raw' && <RawTab detail={detail} />}
            {tab === 'details' && <DetailsTab detail={detail} />}
            {tab === 'history' && <HistoryTab load={loadHistory} />}
          </div>
          {actions.some((a) => a !== 'read') && (
            <footer className="data-inspector-actions">
              {actions.includes('reveal') &&
                (revealedUntil !== null ? (
                  <button type="button" className="data-button" onClick={onHide}>
                    <EyeOff size={14} aria-hidden="true" /> Hide
                  </button>
                ) : (
                  <Hint label="Show the value for a while; recorded in the audit log">
                    <button type="button" className="data-button" onClick={onReveal} disabled={revealing}>
                      <Eye size={14} aria-hidden="true" /> {revealing ? 'Revealing…' : 'Reveal'}
                    </button>
                  </Hint>
                ))}
              {actions.includes('download') && (
                <Hint label="Download" shortcut="D">
                  <button type="button" className="data-button" onClick={onDownload}>
                    <Download size={14} aria-hidden="true" /> Download
                  </button>
                </Hint>
              )}
              {actions.includes('write') && (
                <Hint label="Edit the value" shortcut="E">
                  <button type="button" className="data-button" onClick={onEdit}>
                    <Pencil size={14} aria-hidden="true" /> Edit
                  </button>
                </Hint>
              )}
              <span className="data-spacer" />
              {actions.includes('delete') && (
                <Hint label="Delete" shortcut="⌘⌫">
                  <button type="button" className="data-button data-button-danger-ghost" onClick={onDelete}>
                    <Trash2 size={14} aria-hidden="true" /> {view.deleteLabel ?? 'Delete'}
                  </button>
                </Hint>
              )}
            </footer>
          )}
        </>
      ) : null}
    </aside>
  );
}
