'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { formatBytes, formatMs } from './system-format';
import type { Tone } from './system-model';
import {
  appendTraffic,
  filterTraffic,
  liveSourceLabel,
  summarizeTraffic,
  traceLink,
  type TrafficEvent,
  type TrafficFilters,
} from './system-traffic-model';
import { loadSystem } from './system-api';
import { streamTraffic } from './system-traffic-stream';
import type { TelemetryInfo } from './system-types';
import { Section, SourceNote, Status } from './system-ui';

const KINDS = ['all', 'service', 'transfer', 'model', 'discovery', 'agent', 'job', 'event'];

function statusTone(status: string): Tone {
  if (status === 'ok') return 'ok';
  if (status === 'published') return 'muted';
  if (status === 'no_reply') return 'warn';
  return 'error';
}

function clock(at: number): string {
  const date = new Date(at * 1000);
  return `${date.toLocaleTimeString([], { hour12: false })}.${String(date.getMilliseconds()).padStart(3, '0')}`;
}

function TraceCell({ traceId, uiUrl }: { traceId: string; uiUrl: string | null }) {
  if (!traceId) return <>–</>;
  const href = traceLink(uiUrl, traceId);
  if (!href) return <>{traceId.slice(0, 8)}</>;
  return (
    <a className="system-link" data-trace href={href} target="_blank" rel="noreferrer">
      {traceId.slice(0, 8)}
    </a>
  );
}

/** Filters, per-service summary and the recent calls (presentational). */
export function TrafficView({
  events,
  filters,
  onFilters,
  traceUiUrl = null,
}: {
  events: TrafficEvent[];
  filters: TrafficFilters;
  onFilters: (filters: TrafficFilters) => void;
  traceUiUrl?: string | null;
}) {
  const shown = filterTraffic(events, filters);
  const summary = summarizeTraffic(shown);

  return (
    <>
      <div className="system-traffic-filters">
        <select
          className="system-input"
          value={filters.kind}
          aria-label="Kind"
          onChange={(e) => onFilters({ ...filters, kind: e.target.value })}
        >
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>{kind === 'all' ? 'All kinds' : kind}</option>
          ))}
        </select>
        <input
          className="system-input system-input-grow"
          placeholder="Filter by subject, service, caller, error, trace…"
          value={filters.text}
          onChange={(e) => onFilters({ ...filters, text: e.target.value })}
        />
        <label className="system-checkbox">
          <input
            type="checkbox"
            checked={filters.errorsOnly}
            onChange={(e) => onFilters({ ...filters, errorsOnly: e.target.checked })}
          />
          Errors only
        </label>
      </div>

      <Section title="By service" subtitle={`${shown.length} calls in view`}>
        {summary.length === 0 ? (
          <p className="system-empty">Nothing yet.</p>
        ) : (
          <div className="system-table-wrap">
            <table className="system-table">
              <thead>
                <tr>
                  <th>Kind</th>
                  <th>Service.method</th>
                  <th className="system-num">Calls</th>
                  <th className="system-num">Errors</th>
                  <th className="system-num">Avg latency</th>
                  <th className="system-num">Bytes</th>
                </tr>
              </thead>
              <tbody>
                {summary.map((row) => (
                  <tr key={row.key} className="system-table-row" data-traffic-summary={row.key}>
                    <td>{row.kind}</td>
                    <td className="system-mono">{row.service}.{row.method}</td>
                    <td className="system-num">{row.calls}</td>
                    <td className="system-num">{row.errors}</td>
                    <td className="system-num">{formatMs(row.averageMs)}</td>
                    <td className="system-num">{formatBytes(row.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Recent calls" subtitle="Newest first.">
        {shown.length === 0 ? (
          <p className="system-empty">No calls match.</p>
        ) : (
          <div className="system-table-wrap">
            <table className="system-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Kind</th>
                  <th>Service.method</th>
                  <th>Caller</th>
                  <th className="system-num">Request</th>
                  <th className="system-num">Reply</th>
                  <th className="system-num">Latency</th>
                  <th>Status</th>
                  <th>Trace</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e, index) => (
                  <tr key={`${e.at}-${e.subject}-${index}`} className="system-table-row" data-traffic-row>
                    <td className="system-mono">{clock(e.at)}</td>
                    <td>{e.kind}</td>
                    <td className="system-mono" title={e.subject}>{e.service}.{e.method}</td>
                    <td className={e.caller ? 'system-mono' : 'system-empty-cell'}>{e.caller || '–'}</td>
                    <td className="system-num">{formatBytes(e.request_bytes)}</td>
                    <td className="system-num">{e.reply_bytes === null ? '–' : formatBytes(e.reply_bytes)}</td>
                    <td className="system-num">{e.latency_ms === null ? '–' : formatMs(e.latency_ms)}</td>
                    <td>
                      <Status tone={statusTone(e.status)} label={e.error_code ? `${e.status} ${e.error_code}` : e.status} />
                    </td>
                    <td className="system-mono" title={e.trace_id || undefined}>
                      <TraceCell traceId={e.trace_id} uiUrl={traceUiUrl} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

type StreamState =
  | { state: 'idle' }
  | { state: 'connecting' }
  | { state: 'live'; label: string }
  | { state: 'stopped' }
  | { state: 'ended'; reason: string }
  | { state: 'unavailable'; source?: string; reason: string };

/** Live NATS traffic: runs a tap on the API only while this tab streams. */
export function SystemTraffic() {
  const [stream, setStream] = useState<StreamState>({ state: 'idle' });
  const [events, setEvents] = useState<TrafficEvent[]>([]);
  const [dropped, setDropped] = useState(0);
  const [paused, setPaused] = useState(false);
  const [filters, setFilters] = useState<TrafficFilters>({ kind: 'all', text: '', errorsOnly: false });
  const [traceUiUrl, setTraceUiUrl] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  const stop = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
  }, []);

  const start = useCallback(() => {
    stop();
    const abort = new AbortController();
    controller.current = abort;
    setStream({ state: 'connecting' });
    streamTraffic({
      signal: abort.signal,
      onFrame: (frame) => {
        if (frame.type === 'status') {
          if (frame.state === 'live') setStream({ state: 'live', label: liveSourceLabel(frame.source, frame.skipped) });
          else if (frame.state === 'unavailable') setStream({ state: 'unavailable', source: frame.source ?? undefined, reason: frame.reason ?? '' });
          else setStream({ state: 'ended', reason: frame.reason ?? 'stream ended' });
          return;
        }
        setDropped(frame.dropped);
        if (!pausedRef.current) setEvents((list) => appendTraffic(list, frame.events));
      },
    })
      .then(() => {
        setStream((s) => (s.state === 'live' || s.state === 'connecting' ? { state: 'ended', reason: 'stream ended' } : s));
      })
      .catch((error: unknown) => {
        if (abort.signal.aborted) {
          setStream({ state: 'stopped' });
          return;
        }
        setStream({ state: 'unavailable', reason: error instanceof Error ? error.message : String(error) });
      });
  }, [stop]);

  useEffect(() => stop, [stop]);

  useEffect(() => {
    let cancelled = false;
    loadSystem<TelemetryInfo>('/telemetry').then((loaded) => {
      if (!cancelled && loaded.ok && loaded.data.enabled) setTraceUiUrl(loaded.data.ui_url);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const running = stream.state === 'live' || stream.state === 'connecting';

  return (
    <div className="system-tab-body">
      <div className="system-traffic-bar">
        {running ? (
          <button type="button" className="system-button" onClick={stop}>Stop</button>
        ) : (
          <button type="button" className="system-button system-button-primary" onClick={start}>Start live traffic</button>
        )}
        <button type="button" className="system-button" disabled={!running} onClick={() => setPaused((p) => !p)}>
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button type="button" className="system-button" onClick={() => setEvents([])}>Clear</button>
        <span className="system-traffic-state">
          {stream.state === 'live' && <Status tone="ok" label={paused ? `${stream.label} (paused)` : stream.label} />}
          {stream.state === 'connecting' && <Status tone="warn" label="Connecting…" />}
          {stream.state === 'stopped' && <Status tone="muted" label="Stopped" />}
          {stream.state === 'ended' && <Status tone="muted" label={`Ended: ${stream.reason}`} />}
          {dropped > 0 && <span className="system-traffic-dropped">{dropped} dropped (viewer too slow)</span>}
        </span>
      </div>
      <p className="system-footnote">
        Metadata only: payloads and tokens are never read. From traces, each call is its span (the
        caller is the process that made it; a file transfer is one row with its total size). From the
        NATS bus (fallback), the API receives every reply while this runs; stop it when you are done.
      </p>
      {stream.state === 'unavailable' && <SourceNote label="Live traffic" reason={stream.reason} />}
      <TrafficView events={events} filters={filters} onFilters={setFilters} traceUiUrl={traceUiUrl} />
    </div>
  );
}
