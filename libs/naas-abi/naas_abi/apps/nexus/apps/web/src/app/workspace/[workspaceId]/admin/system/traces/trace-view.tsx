'use client';

/** A whole trace: header, waterfall, and the selected span's detail. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ExternalLink, Maximize2, Waypoints } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { absoluteTime } from '../data/data-model';
import { Badge, CopyButton, EmptyState, RelativeTime, SkeletonRows } from '../data/data-ui';
import type { TracesApi } from './traces-api';
import { buildRows, formatSpanMs, serviceColor } from './traces-model';
import type { Trace } from './traces-types';
import { SpanDetail } from './span-detail';
import { Waterfall } from './waterfall';

export function useTrace(api: TracesApi, traceId: string | null): { trace: Trace | null; failure: Failure | null } {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  useEffect(() => {
    setTrace(null);
    setFailure(null);
    if (!traceId) return;
    let cancelled = false;
    void api.trace(traceId).then((result) => {
      if (cancelled) return;
      if (result.ok) setTrace(result.data);
      else setFailure(result);
    });
    return () => {
      cancelled = true;
    };
  }, [api, traceId]);
  return { trace, failure };
}

export function TraceHeader({
  trace,
  uiUrl,
  onExpand,
}: {
  trace: Trace;
  uiUrl?: string | null;
  onExpand?: () => void;
}) {
  const root = useMemo(() => buildRows(trace)[0]?.span, [trace]);
  const errors = trace.services.reduce((n, s) => n + s.errors, 0);
  return (
    <header className="trace-header">
      <div className="trace-header-main">
        <h2 className="trace-title" title={root?.name}>
          {root ? (
            <>
              <span className="trace-title-service" style={{ color: serviceColor(root.service) }}>
                {root.service}
              </span>{' '}
              {root.name}
            </>
          ) : (
            'Trace'
          )}
        </h2>
        <div className="trace-id">
          <code className="data-mono">{trace.trace_id}</code>
          <CopyButton value={trace.trace_id} label="Copy trace id" />
        </div>
      </div>
      <dl className="trace-stats">
        <div>
          <dt>Started</dt>
          <dd title={absoluteTime(trace.start)}>
            <RelativeTime iso={trace.start} />
          </dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatSpanMs(trace.duration_ms)}</dd>
        </div>
        <div>
          <dt>Spans</dt>
          <dd>{trace.spans.length}</dd>
        </div>
        <div>
          <dt>Errors</dt>
          <dd className={errors ? 'trace-stat-error' : undefined}>{errors}</dd>
        </div>
      </dl>
      <div className="trace-services">
        {trace.services.map((s) => (
          <span key={s.name} className="trace-service-chip">
            <span className="trace-service-dot" style={{ backgroundColor: serviceColor(s.name) }} aria-hidden="true" />
            {s.name}
            <span className="data-muted">{s.spans}</span>
            {s.errors > 0 && <Badge tone="danger">{s.errors} err</Badge>}
          </span>
        ))}
        <span className="data-spacer" />
        {onExpand && (
          <button type="button" className="data-text-button" onClick={onExpand}>
            <Maximize2 size={12} aria-hidden="true" /> Open in Traces
          </button>
        )}
        {uiUrl && (
          <a className="data-text-button" href={`${uiUrl.replace(/\/$/, '')}/trace/${trace.trace_id}`} target="_blank" rel="noopener noreferrer">
            Jaeger <ExternalLink size={11} aria-hidden="true" />
          </a>
        )}
      </div>
    </header>
  );
}

export function TraceView({
  api,
  traceId,
  compact = false,
  uiUrl,
  selectedSpan,
  onSelectSpan,
  onOpenTrace,
  onExpand,
}: {
  api: TracesApi;
  traceId: string;
  compact?: boolean;
  uiUrl?: string | null;
  selectedSpan?: string | null;
  onSelectSpan?: (spanId: string | null) => void;
  onOpenTrace?: (traceId: string) => void;
  onExpand?: () => void;
}) {
  const { trace, failure } = useTrace(api, traceId);
  const [localSpan, setLocalSpan] = useState<string | null>(null);
  const spanId = selectedSpan !== undefined ? selectedSpan : localSpan;
  const select = (id: string | null) => (onSelectSpan ? onSelectSpan(id) : setLocalSpan(id));
  const span = trace?.spans.find((s) => s.span_id === spanId) ?? null;
  const side = useRef<HTMLElement>(null);

  // Embedded, the detail opens below the waterfall: bring it into view.
  useEffect(() => {
    if (compact && span) side.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  }, [compact, span?.span_id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (failure) {
    return (
      <EmptyState icon={failure.status === 404 ? Waypoints : AlertTriangle} title={failure.status === 404 ? 'Trace not found' : 'Could not load the trace'}>
        {failure.status === 404
          ? 'It may not be exported yet (spans arrive within a second or two), or the tracing backend no longer keeps it.'
          : failure.reason}
      </EmptyState>
    );
  }
  if (!trace) return <SkeletonRows rows={5} />;

  return (
    <div className={compact ? 'trace-view trace-view-compact' : 'trace-view'}>
      <TraceHeader trace={trace} uiUrl={uiUrl} onExpand={onExpand} />
      <div className="trace-body">
        <div className="trace-main">
          <Waterfall trace={trace} selected={spanId} onSelect={(id) => select(id === spanId ? null : id)} />
        </div>
        {span && (
          <aside ref={side} className="trace-side" aria-label="Selected span">
            <SpanDetail span={span} trace={trace} onSelect={select} onOpenTrace={onOpenTrace} onClose={() => select(null)} />
          </aside>
        )}
      </div>
    </div>
  );
}
