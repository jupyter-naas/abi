/** Wire types of /api/admin/system/traces (sysadmin traces domain). */

export type SpanKind = 'server' | 'client' | 'producer' | 'consumer' | 'internal' | '';
export type Scalar = string | number | boolean;

export interface ServiceCount {
  name: string;
  spans: number;
  errors: number;
}

export interface TraceSummary {
  trace_id: string;
  root: { service: string; name: string };
  start: string;
  duration_ms: number;
  spans: number;
  errors: number;
  services: ServiceCount[];
}

export interface SpanEvent {
  name: string;
  offset_ms: number;
  attributes: Record<string, Scalar>;
}

export interface Span {
  span_id: string;
  parent_id: string | null;
  name: string;
  service: string;
  kind: SpanKind | string;
  start_ms: number;
  duration_ms: number;
  status: 'ok' | 'error' | 'unset' | string;
  status_message: string;
  attributes: Record<string, Scalar>;
  resource: Record<string, Scalar>;
  events: SpanEvent[];
  links: { trace_id: string; span_id: string }[];
}

export interface Trace {
  trace_id: string;
  start: string;
  duration_ms: number;
  services: ServiceCount[];
  spans: Span[];
  truncated: boolean;
}

export interface TraceQuery {
  service?: string | null;
  operation?: string | null;
  lookback?: string;
  min_duration_ms?: number | null;
  max_duration_ms?: number | null;
  errors?: boolean;
  limit?: number;
}
