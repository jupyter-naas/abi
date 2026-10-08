'use client';

/** One span: timing, ids, attributes by namespace, events, resource and links. */
import { AlertTriangle, ArrowUpRight, X } from 'lucide-react';
import { Badge, CopyButton, Hint, Notice } from '../data/data-ui';
import { formatSpanMs, groupAttributes, selfTime, serviceColor } from './traces-model';
import type { Scalar, Span, Trace } from './traces-types';

function Value({ value }: { value: Scalar | unknown }) {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return (
    <span className="span-value">
      <span className={typeof value === 'string' ? 'span-value-text' : 'span-value-literal'}>{text}</span>
      <CopyButton value={text} label="Copy value" />
    </span>
  );
}

function Table({ entries }: { entries: [string, unknown][] }) {
  return (
    <table className="data-kv span-kv">
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <th title={key}>{key}</th>
            <td>
              <Value value={value} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SpanDetail({
  span,
  trace,
  onSelect,
  onOpenTrace,
  onClose,
}: {
  span: Span;
  trace: Trace;
  onSelect: (spanId: string) => void;
  onOpenTrace?: (traceId: string) => void;
  onClose?: () => void;
}) {
  const parent = span.parent_id ? trace.spans.find((s) => s.span_id === span.parent_id) : undefined;
  const children = trace.spans.filter((s) => s.parent_id === span.span_id);
  const share = trace.duration_ms ? (span.duration_ms / trace.duration_ms) * 100 : 0;
  const self = selfTime(span, children);
  return (
    <div className="span-detail">
      <header className="span-detail-header">
        <span className="span-detail-chip" style={{ backgroundColor: serviceColor(span.service) }} aria-hidden="true" />
        <div className="span-detail-heading">
          <h3 className="span-detail-name" title={span.name}>
            {span.name}
          </h3>
          <p className="span-detail-service">
            {span.service}
            {span.kind && <Badge>{span.kind}</Badge>}
            {span.status === 'error' ? (
              <Badge tone="danger">error</Badge>
            ) : span.status === 'ok' ? (
              <Badge tone="success">ok</Badge>
            ) : null}
          </p>
        </div>
        {onClose && (
          <Hint label="Close">
            <button type="button" className="data-icon-button" aria-label="Close span" onClick={onClose}>
              <X size={15} aria-hidden="true" />
            </button>
          </Hint>
        )}
      </header>

      {span.status === 'error' && span.status_message && (
        <Notice tone="danger">
          <AlertTriangle size={14} aria-hidden="true" />
          <span className="span-error">{span.status_message}</span>
        </Notice>
      )}

      <dl className="span-facts">
        <div>
          <dt>Duration</dt>
          <dd>{formatSpanMs(span.duration_ms)}</dd>
        </div>
        <div>
          <dt>Self</dt>
          <dd>{formatSpanMs(self)}</dd>
        </div>
        <div>
          <dt>Starts at</dt>
          <dd>+{formatSpanMs(span.start_ms)}</dd>
        </div>
        <div>
          <dt>Of the trace</dt>
          <dd>{share.toFixed(share < 10 ? 1 : 0)}%</dd>
        </div>
      </dl>

      <dl className="span-ids">
        <div>
          <dt>Span</dt>
          <dd>
            <code className="data-mono">{span.span_id}</code>
            <CopyButton value={span.span_id} label="Copy span id" />
          </dd>
        </div>
        <div>
          <dt>Parent</dt>
          <dd>
            {parent ? (
              <button type="button" className="data-link" onClick={() => onSelect(parent.span_id)}>
                {parent.name}
              </button>
            ) : span.parent_id ? (
              <code className="data-mono" title="Not in this trace">
                {span.parent_id}
              </code>
            ) : (
              <span className="data-muted">root</span>
            )}
          </dd>
        </div>
        {children.length > 0 && (
          <div>
            <dt>Children</dt>
            <dd>{children.length}</dd>
          </div>
        )}
      </dl>

      {groupAttributes(span.attributes).map((group) => (
        <section key={group.label} className="data-section">
          <h4 className="data-section-title">{group.label}</h4>
          <Table entries={group.entries} />
        </section>
      ))}

      {span.events.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Events · {span.events.length}</h4>
          <ol className="span-events">
            {span.events.map((event, i) => (
              <li key={i} className="span-event">
                <span className="span-event-time">+{formatSpanMs(event.offset_ms)}</span>
                <div className="span-event-body">
                  <p className="span-event-name">{event.name}</p>
                  {Object.keys(event.attributes).length > 0 && <Table entries={Object.entries(event.attributes)} />}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {Object.keys(span.resource).length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Resource</h4>
          <Table entries={Object.entries(span.resource).sort(([a], [b]) => a.localeCompare(b))} />
        </section>
      )}

      {span.links.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Links · {span.links.length}</h4>
          <ul className="span-links">
            {span.links.map((link) => (
              <li key={`${link.trace_id}-${link.span_id}`}>
                {onOpenTrace ? (
                  <button type="button" className="data-link" onClick={() => onOpenTrace(link.trace_id)}>
                    {link.trace_id} <ArrowUpRight size={11} aria-hidden="true" />
                  </button>
                ) : (
                  <code className="data-mono">{link.trace_id}</code>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
