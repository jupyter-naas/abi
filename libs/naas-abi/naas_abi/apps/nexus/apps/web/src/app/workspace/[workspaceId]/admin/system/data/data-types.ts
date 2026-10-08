/** Wire types of /api/admin/system/resources (sysadmin resources.py). */

export interface ResourceCapabilities {
  browse: boolean;
  lookup: boolean;
  create: boolean;
  reveal: boolean;
  write_format: string;
  search: boolean;
  /** Items can be written with an expiry (``ttl_seconds``). */
  expiry?: boolean;
}

export interface ResourceServiceInfo {
  name: string;
  available: boolean;
  reason: string;
  capabilities: ResourceCapabilities;
}

export type ResourceAction = 'read' | 'download' | 'write' | 'delete' | 'reveal';

export interface ResourceEntry {
  id: string;
  name: string;
  kind: 'container' | 'item';
  actions: ResourceAction[];
  size: number | null;
  modified: string | null;
  attributes: Record<string, string>;
}

export interface ResourcePage {
  parent: string;
  entries: ResourceEntry[];
  next_cursor: string | null;
  /** False when the service cannot enumerate this container: open entries by id. */
  listable: boolean;
}

export interface ResourceContent {
  encoding: 'text' | 'binary' | 'masked';
  text: string | null;
  size: number | null;
  truncated: boolean;
}

/** Structured shapes an adapter may attach for rich rendering (see resources.py). */
export type ResourceView =
  | { type: 'json'; value: unknown }
  | { type: 'table'; columns: { name: string; type?: string }[]; rows: unknown[][]; total?: number | null }
  | { type: 'triples'; triples: [string, string, string][]; prefixes?: Record<string, string>; total?: number | null }
  | {
      type: 'vector';
      dimension: number;
      components: number[];
      norm?: number | null;
      metadata?: unknown;
      payload?: unknown;
    }
  | {
      type: 'email';
      from?: string;
      to?: string[] | string;
      cc?: string[] | string;
      subject?: string;
      text?: string;
      html?: string;
      sent_at?: string;
    }
  | {
      type: 'message';
      subject?: string;
      headers?: Record<string, string>;
      sequence?: number;
      published_at?: string;
    }
  | { type: 'status'; phase?: string; fields?: Record<string, unknown> }
  | ({ type: 'checkpoint' } & CheckpointView)
  | { type: string; [key: string]: unknown };

/** A LangGraph message as the API decodes it (``langgraph_checkpoints.py``). */
export interface CheckpointMessage {
  role: 'human' | 'ai' | 'tool' | 'system' | string;
  content: string;
  truncated?: number;
  name?: string;
  id?: string;
  tool_call_id?: string;
  status?: string;
  tool_calls?: { id?: string | null; name?: string | null; args?: unknown }[];
  usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
  model?: string;
}

export interface CheckpointWrite {
  task_id?: string | null;
  task_path?: string | null;
  channel?: string | null;
  index?: number | null;
  value: unknown;
}

/** One LangGraph checkpoint: a thread's state after a step. */
export interface CheckpointView {
  agent_id?: string | null;
  thread_id?: string | null;
  checkpoint_ns?: string | null;
  checkpoint_id?: string | null;
  parent_id?: string | null;
  /** The previous step's entry id, to open it. */
  parent_entry?: string | null;
  created_at?: string | null;
  step?: number | null;
  source?: string | null;
  messages: CheckpointMessage[];
  channels: Record<string, unknown>;
  metadata: Record<string, unknown>;
  writes: CheckpointWrite[];
}

export interface ResourceDetail {
  entry: ResourceEntry;
  content: ResourceContent | null;
  view?: ResourceView | null;
}

export interface AuditEntry {
  at: string;
  actor_id: string;
  actor: string;
  service: string;
  operation: 'create' | 'replace' | 'delete' | 'reveal' | string;
  resource_id: string;
  phase: 'requested' | 'succeeded' | 'failed' | string;
  error: string;
}
