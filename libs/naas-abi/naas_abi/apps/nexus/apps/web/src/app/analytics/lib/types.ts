export type EventName =
  | 'session_started'
  | 'session_ended'
  | 'page_viewed'
  | 'workspace_opened'
  | 'workspace_created'
  | 'workspace_updated'
  | 'file_uploaded'
  | 'button_clicked'
  | 'search_performed'
  | 'export_clicked'
  | 'invite_sent'
  | 'login'
  | 'logout'
  | 'error_seen';

export interface AnalyticsEvent {
  event_id: string;
  timestamp: string;
  user_id?: string;
  user_email?: string;
  workspace_id?: string;
  workspace_name?: string;
  session_id: string;
  event_name: EventName;
  page_path?: string;
  page_title?: string;
  properties?: Record<string, unknown>;
  device?: string;
  browser?: string;
  country?: string;
  referrer?: string;
}

export type ScenarioId = 'last_7_days' | 'last_30_days' | 'last_90_days';

export interface Scenario {
  scenario: string;
  scenario_id: ScenarioId;
  date_start: string;
  date_end: string;
}

export interface ScenariosResponse {
  scenarios: Scenario[];
}

export interface AnalyticsFilters {
  scenario_id: ScenarioId;
  user_email?: string;
  workspace_id?: string;
}

export interface TimeseriesPoint {
  date: string;
  value: number;
}

export interface OverviewKpi {
  active_users: number;
  total_sessions: number;
  avg_sessions_per_user: number;
  total_page_views: number;
  workspaces_used: number;
  avg_session_duration_seconds: number;
  returning_users: number;
  most_active_workspace: { id: string; name: string; events: number } | null;
}

export interface UserRow {
  user_id: string;
  user_email: string;
  sessions: number;
  page_views: number;
  workspaces: number;
  last_seen: string;
  total_events: number;
}

export interface PageRow {
  page_path: string;
  page_title: string;
  views: number;
  unique_users: number;
}

export interface WorkspaceRow {
  workspace_id: string;
  workspace_name: string;
  active_users: number;
  sessions: number;
  events: number;
}

export interface SessionRow {
  session_id: string;
  user_email: string;
  workspace_name?: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  page_views: number;
  events: number;
  device?: string;
  browser?: string;
}

export interface UserDetail {
  user_email: string;
  user_id: string;
  first_seen: string;
  last_seen: string;
  total_sessions: number;
  total_page_views: number;
  workspaces_used: { id: string; name: string }[];
  most_visited_page: { path: string; title: string; views: number } | null;
  sessions: SessionRow[];
  pages: PageRow[];
  events: AnalyticsEvent[];
}

export interface OverviewResponse {
  kpi: OverviewKpi;
  sessions_over_time: TimeseriesPoint[];
  active_users_over_time: TimeseriesPoint[];
  top_users: UserRow[];
  top_pages: PageRow[];
  workspace_activity: WorkspaceRow[];
  recent_activity: AnalyticsEvent[];
}

export interface ChatRow {
  conversation_id: string;
  title: string;
  chat_title?: string | null;
  workspace_id?: string | null;
  workspace_name?: string | null;
  user_email?: string | null;
  first_viewed_at: string;
  last_viewed_at: string;
  page_views: number;
  message_count: number;
}

export interface ChatsResponse {
  chats: ChatRow[];
}

export interface ChatMessageStep {
  tool_name: string;
  prefix: string;
  status: string;
  input?: string | null;
  output?: string | null;
}

export type ChatMessageFeedback = 'like' | 'dislike';

export interface ChatMessageMetadata {
  execution_time?: number | null;
  steps?: ChatMessageStep[];
  sources?: string[];
  feedback?: ChatMessageFeedback | null;
  [key: string]: unknown;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | string;
  content: string;
  agent?: string | null;
  created_at?: string | null;
  metadata?: ChatMessageMetadata | null;
}

export interface ChatDetail {
  conversation_id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  agent: string;
  created_at?: string | null;
  updated_at?: string | null;
  messages: ChatMessage[];
}
