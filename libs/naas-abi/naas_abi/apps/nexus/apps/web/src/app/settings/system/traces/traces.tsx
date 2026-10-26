'use client';

/**
 * The Traces tab: find traces (service, operation, window, duration, errors) and
 * read one as a waterfall with each span's attributes and events. The tracing
 * backend (Jaeger) stays behind the API; nothing here needs its UI.
 */
import '../data/data.css';
import './traces.css';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import * as Tooltip from '@radix-ui/react-tooltip';
import { AlertTriangle, ChevronRight, RefreshCw, Search, Waypoints } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { absoluteTime } from '../data/data-model';
import { Badge, EmptyState, Hint, IconTile, Notice, RelativeTime, SkeletonRows } from '../data/data-ui';
import { Scatter } from './scatter';
import { TraceView } from './trace-view';
import { createTracesApi, type TracesApi } from './traces-api';
import { LOOKBACKS, formatSpanMs, isTraceId, serviceColor } from './traces-model';
import type { TraceQuery, TraceSummary } from './traces-types';

interface Location {
  trace: string | null;
  span: string | null;
  service: string;
  operation: string;
  lookback: string;
  errors: boolean;
  minMs: string;
}

function decode(params: URLSearchParams): Location {
  return {
    trace: params.get('trace'),
    span: params.get('span'),
    service: params.get('service') ?? '',
    operation: params.get('operation') ?? '',
    lookback: params.get('lookback') ?? '1h',
    errors: params.get('errors') === 'true',
    minMs: params.get('min_ms') ?? '',
  };
}

function encode(location: Location, params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params.toString());
  const set = (key: string, value: string | null) => (value ? next.set(key, value) : next.delete(key));
  set('trace', location.trace);
  set('span', location.trace ? location.span : null);
  set('service', location.service);
  set('operation', location.operation);
  set('lookback', location.lookback === '1h' ? null : location.lookback);
  set('errors', location.errors ? 'true' : null);
  set('min_ms', location.minMs);
  return next;
}

function ResultRow({ trace, longest, onOpen }: { trace: TraceSummary; longest: number; onOpen: () => void }) {
  return (
    <div role="option" aria-selected={false} tabIndex={-1} className="trace-result" data-trace={trace.trace_id} onClick={onOpen}>
      <div className="trace-result-main">
        <p className="trace-result-title">
          <span className="trace-service-dot" style={{ backgroundColor: serviceColor(trace.root.service) }} aria-hidden="true" />
          <span className="trace-result-service">{trace.root.service}</span>
          <span className="trace-result-name">{trace.root.name}</span>
          {trace.errors > 0 && (
            <Badge tone="danger">
              {trace.errors} error{trace.errors === 1 ? '' : 's'}
            </Badge>
          )}
        </p>
        <p className="trace-result-services">
          {trace.services.slice(0, 6).map((s) => (
            <span key={s.name} className="trace-service-chip trace-service-chip-sm">
              <span className="trace-service-dot" style={{ backgroundColor: serviceColor(s.name) }} aria-hidden="true" />
              {s.name} <span className="data-muted">{s.spans}</span>
            </span>
          ))}
          {trace.services.length > 6 && <span className="data-muted">+{trace.services.length - 6}</span>}
        </p>
      </div>
      <div className="trace-result-side">
        <span className="trace-result-duration">{formatSpanMs(trace.duration_ms)}</span>
        <span className="trace-result-bar">
          <span style={{ width: `${Math.max(2, (trace.duration_ms / Math.max(longest, 1e-6)) * 100)}%` }} />
        </span>
        <span className="data-muted trace-result-when" title={absoluteTime(trace.start)}>
          {trace.spans} spans · <RelativeTime iso={trace.start} />
        </span>
      </div>
    </div>
  );
}

export function TracesTab({ api: injected, nonce = 0 }: { api?: TracesApi; nonce?: number }) {
  const api = useMemo(() => injected ?? createTracesApi(), [injected]);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [location, setLocation] = useState<Location>(() => decode(new URLSearchParams(params.toString())));
  const [services, setServices] = useState<string[] | null>(null);
  const [uiUrl, setUiUrl] = useState<string | null>(null);
  const [operations, setOperations] = useState<string[]>([]);
  const [results, setResults] = useState<TraceSummary[] | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [reloads, setReloads] = useState(0);
  const [jump, setJump] = useState('');

  useEffect(() => {
    const encoded = encode(location, new URLSearchParams(params.toString()));
    if (encoded.toString() !== params.toString()) router.replace(`${pathname}?${encoded.toString()}`, { scroll: false });
  }, [location]); // eslint-disable-line react-hooks/exhaustive-deps

  const go = (patch: Partial<Location>) => setLocation((l) => ({ ...l, ...patch }));

  useEffect(() => {
    void api.services().then((result) => {
      if (result.ok) {
        setServices(result.data.services);
        setUiUrl(result.data.ui_url);
      } else setFailure(result);
    });
  }, [api, nonce]);

  useEffect(() => {
    setOperations([]);
    if (!location.service) return;
    void api.operations(location.service).then((result) => {
      if (result.ok) setOperations([...new Set(result.data.operations.map((o) => o.name))].sort());
    });
  }, [api, location.service]);

  const q: TraceQuery = useMemo(
    () => ({
      service: location.service || null,
      operation: location.operation || null,
      lookback: location.lookback,
      errors: location.errors,
      min_duration_ms: location.minMs ? Number(location.minMs) : null,
      limit: 50,
    }),
    [location.service, location.operation, location.lookback, location.errors, location.minMs],
  );

  useEffect(() => {
    if (location.trace) return;
    let cancelled = false;
    setResults(null);
    void api.search(q).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        setResults(result.data.traces);
        setFailure(null);
      } else {
        setResults([]);
        setFailure(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [api, q, location.trace, reloads, nonce]);

  const longest = Math.max(0, ...(results ?? []).map((t) => t.duration_ms));
  const open = (traceId: string) => go({ trace: traceId.toLowerCase(), span: null });

  return (
    <Tooltip.Provider>
      <div className="data-explorer traces-root">
        <section className="data-main" aria-label="Traces">
          <header className="data-service-header">
            <IconTile icon={Waypoints} size="lg" />
            <div className="data-service-heading">
              <h2 className="data-service-title">Traces</h2>
              <p className="data-service-description">
                Every request, NATS call, job and agent run, end to end across processes.
              </p>
            </div>
            <div className="data-service-actions">
              <form
                className="trace-jump"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (isTraceId(jump)) {
                    open(jump.trim());
                    setJump('');
                  }
                }}
              >
                <input
                  className="data-input data-input-sm"
                  placeholder="Go to trace id"
                  aria-label="Go to trace id"
                  value={jump}
                  onChange={(e) => setJump(e.target.value)}
                  spellCheck={false}
                />
              </form>
              {!location.trace && (
                <Hint label="Search again">
                  <button
                    type="button"
                    className="data-icon-button data-icon-button-bordered"
                    aria-label="Search again"
                    onClick={() => setReloads((n) => n + 1)}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                  </button>
                </Hint>
              )}
            </div>
          </header>
          <div className="data-toolbar">
            <nav className="data-crumbs" aria-label="Path">
              <span className="data-crumb">
                {location.trace ? (
                  <button type="button" className="data-crumb-link" onClick={() => go({ trace: null, span: null })}>
                    Search
                  </button>
                ) : (
                  <span className="data-crumb-current">Search</span>
                )}
              </span>
              {location.trace && (
                <span className="data-crumb">
                  <ChevronRight size={12} aria-hidden="true" className="data-crumb-sep" />
                  <span className="data-crumb-current data-mono">{location.trace.slice(0, 16)}…</span>
                </span>
              )}
            </nav>
            {!location.trace && (
              <div className="trace-filters">
                <select
                  className="data-input data-input-sm"
                  aria-label="Service"
                  value={location.service}
                  onChange={(e) => go({ service: e.target.value, operation: '' })}
                >
                  <option value="">All services</option>
                  {(services ?? []).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <select
                  className="data-input data-input-sm"
                  aria-label="Operation"
                  value={location.operation}
                  disabled={!location.service}
                  onChange={(e) => go({ operation: e.target.value })}
                >
                  <option value="">All operations</option>
                  {operations.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
                <select
                  className="data-input data-input-sm"
                  aria-label="Time window"
                  value={location.lookback}
                  onChange={(e) => go({ lookback: e.target.value })}
                >
                  {LOOKBACKS.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
                <input
                  className="data-input data-input-sm trace-min"
                  type="number"
                  min={0}
                  placeholder="Min ms"
                  aria-label="Minimum duration in ms"
                  value={location.minMs}
                  onChange={(e) => go({ minMs: e.target.value })}
                />
                <label className="trace-errors-toggle">
                  <input type="checkbox" checked={location.errors} onChange={(e) => go({ errors: e.target.checked })} />
                  Errors only
                </label>
              </div>
            )}
          </div>
          <div className={location.trace ? 'traces-body traces-body-trace' : 'data-browser traces-body'}>
            {failure && (
              <Notice tone={failure.source === 'tracing' ? 'warn' : 'danger'}>
                <AlertTriangle size={14} aria-hidden="true" /> {failure.reason}
              </Notice>
            )}
            {location.trace ? (
              <TraceView
                api={api}
                traceId={location.trace}
                uiUrl={uiUrl}
                selectedSpan={location.span}
                onSelectSpan={(span) => go({ span })}
                onOpenTrace={open}
              />
            ) : results === null ? (
              <SkeletonRows rows={6} />
            ) : results.length === 0 ? (
              !failure && (
                <EmptyState icon={Search} title="No traces match">
                  Widen the time window, pick another service, or clear the duration and error filters.
                </EmptyState>
              )
            ) : (
              <>
                <Scatter traces={results} onOpen={open} />
                <div className="trace-results" role="listbox" aria-label="Traces">
                  {results.map((t) => (
                    <ResultRow key={t.trace_id} trace={t} longest={longest} onOpen={() => open(t.trace_id)} />
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </Tooltip.Provider>
  );
}
