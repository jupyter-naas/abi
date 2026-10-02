/** JSON returned by /api/admin/system/* (see the API's sysadmin domain). */

export interface SourceStatus {
  available: boolean;
  reason: string;
}

export interface EndpointStats {
  name: string;
  subject: string;
  requests: number;
  errors: number;
  average_ms: number;
  last_error: string;
}

export interface MicroServiceInstance {
  name: string;
  instance_id: string;
  version: string;
  started: string;
  endpoints: EndpointStats[];
  requests: number;
  errors: number;
}

export type KernelServiceStatus = 'serving' | 'silent' | 'not_exposed';

export interface KernelService {
  name: string;
  adapters: string[];
  nats_service: string | null;
  instances: MicroServiceInstance[];
  status: KernelServiceStatus;
}

export interface KernelServicesView {
  services: KernelService[];
  sources: Record<string, SourceStatus>;
}

export interface JobSummary {
  name: string;
  description: string;
  triggers: string[];
  max_concurrency: number;
  max_attempts: number;
  timeout_seconds: number | null;
}

export interface EngineModule {
  module_id: string;
  name: string;
  description: string;
  agents: number;
  orchestrations: number;
  ontologies: number;
  jobs: JobSummary[];
}

export interface RemoteModuleInstance {
  module_id: string;
  instance_id: string;
  package_version: string;
  contract_major: number;
  status: string;
  expires_at: number;
  agents: string[];
  jobs: JobSummary[];
}

export interface ModulesView {
  engine: EngineModule[];
  remote: RemoteModuleInstance[];
  sources: Record<string, SourceStatus>;
}

export interface NatsServer {
  server_id: string;
  server_name: string;
  version: string;
  uptime: string;
  connections: number;
  total_connections: number;
  subscriptions: number;
  slow_consumers: number;
  in_msgs: number;
  out_msgs: number;
  in_bytes: number;
  out_bytes: number;
  mem_bytes: number;
  cpu_percent: number;
  max_payload: number;
  jetstream: boolean;
}

export interface NatsConnection {
  cid: number;
  name: string;
  ip: string;
  port: number;
  lang: string;
  version: string;
  uptime: string;
  rtt: string;
  subscriptions: number;
  pending_bytes: number;
  in_msgs: number;
  out_msgs: number;
  in_bytes: number;
  out_bytes: number;
}

export interface JetStreamConsumer {
  name: string;
  filter_subject: string;
  pending: number;
  ack_pending: number;
  redelivered: number;
  waiting: number;
}

export interface JetStreamStream {
  name: string;
  subjects: string[];
  messages: number;
  bytes: number;
  first_seq: number;
  last_seq: number;
  consumer_count: number;
  consumers: JetStreamConsumer[];
  kind: 'kv' | 'jobs' | 'bus' | 'other';
}

export interface JetStreamSummary {
  streams: JetStreamStream[];
  memory_bytes: number;
  storage_bytes: number;
  api_requests: number;
  api_errors: number;
  consumers: number;
  messages: number;
}

export interface TelemetryInfo {
  enabled: boolean;
  service_name: string;
  ui_url: string | null;
}

export interface Overview {
  sources: Record<string, SourceStatus>;
  kernel_services: number;
  serving_services: number;
  service_instances: number;
  requests: number;
  engine_modules: number;
  remote_modules: Record<string, number>;
  server: NatsServer | null;
  jetstream_streams: number;
  jetstream_consumers: number;
  jetstream_messages: number;
  telemetry: TelemetryInfo | null;
}
