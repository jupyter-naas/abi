/** Wire types of /api/admin/system/agents (sysadmin agents domain). */

export type AgentRunStatus =
  | 'ACCEPTED'
  | 'RUNNING'
  | 'CANCELLING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'
  | 'TIMED_OUT';

export interface AgentRunSummary {
  key: string;
  module_id: string;
  run_id: string;
  agent: string;
  invocation_id: string;
  status: AgentRunStatus | string;
  thread_id: string;
  caller: string;
  owner: string;
  submitted_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error_code: string;
  error_message: string;
  trace_id: string;
  events: number;
}

export interface AgentEvent {
  sequence: number;
  event: string;
  preview: string;
  truncated: boolean;
}

export interface AgentRunDetail extends AgentRunSummary {
  event_list: AgentEvent[];
  trace_url: string | null;
}

export interface AgentRunsPage {
  runs: AgentRunSummary[];
  next: string | null;
}
