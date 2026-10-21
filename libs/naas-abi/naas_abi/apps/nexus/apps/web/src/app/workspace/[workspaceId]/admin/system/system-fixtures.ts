/** Sample API payloads for the System app tests (mirror the API's test deployment). */
import type { JetStreamSummary, KernelServicesView, ModulesView, NatsConnection, NatsServer } from './system-types';

const endpoint = (service: string, requests: number) => ({
  name: 'get',
  subject: `abi.svc.${service}.v1.get`,
  requests,
  errors: 0,
  average_ms: requests ? 1.5 : 0,
  last_error: '',
});

export const servicesView: KernelServicesView = {
  services: [
    {
      name: 'document',
      adapters: ['postgresql'],
      nats_service: 'document',
      status: 'serving',
      instances: [
        { name: 'document', instance_id: 'd1', version: '1.0.0', started: '2026-10-02T08:00:00Z', endpoints: [endpoint('document', 3)], requests: 3, errors: 0 },
        { name: 'document', instance_id: 'd2', version: '1.0.0', started: '2026-10-02T08:00:00Z', endpoints: [endpoint('document', 2)], requests: 2, errors: 0 },
      ],
    },
    { name: 'secret', adapters: ['dotenv', 'naas'], nats_service: 'secret', status: 'silent', instances: [] },
    { name: 'bus', adapters: ['nats'], nats_service: null, status: 'not_exposed', instances: [] },
  ],
  sources: { nats: { available: true, reason: '' } },
};

const digest = { name: 'digest', description: 'Counts runs.', triggers: ['every 10m'], max_concurrency: 1, max_attempts: 1, timeout_seconds: 60 };

export const modulesView: ModulesView = {
  engine: [
    {
      module_id: 'acme.jobs', name: 'Acme jobs', description: '', agents: 1, orchestrations: 0, ontologies: 2,
      jobs: [{ ...digest, name: 'nightly', triggers: ['cron 0 0 2 * * * UTC'] }],
    },
  ],
  remote: [
    { module_id: 'ops.researcher', instance_id: 'r-1', package_version: '0.1.0', contract_major: 1, status: 'READY', expires_at: 4_000_000_000, agents: ['Researcher'], jobs: [digest] },
    { module_id: 'ops.researcher', instance_id: 'r-2', package_version: '0.1.0', contract_major: 1, status: 'STARTING', expires_at: 4_000_000_000, agents: ['Researcher'], jobs: [digest] },
  ],
  sources: { discovery: { available: true, reason: '' } },
};

export const natsServer: NatsServer = {
  server_id: 'NSRV', server_name: 'nats', version: '2.14.7', uptime: '1h2m', connections: 2, total_connections: 9,
  subscriptions: 40, slow_consumers: 0, in_msgs: 10, out_msgs: 12, in_bytes: 100, out_bytes: 120,
  mem_bytes: 2048, cpu_percent: 0.5, max_payload: 8 * 1024 * 1024, jetstream: true,
};

export const natsConnections: NatsConnection[] = [
  { cid: 1, name: 'api', ip: '10.0.0.2', port: 51000, lang: 'python3', version: '2.16.0', uptime: '1h', rtt: '1ms', subscriptions: 12, pending_bytes: 0, in_msgs: 5, out_msgs: 6, in_bytes: 50, out_bytes: 60 },
  { cid: 2, name: '', ip: '10.0.0.3', port: 51001, lang: 'python3', version: '2.16.0', uptime: '5m', rtt: '2ms', subscriptions: 3, pending_bytes: 0, in_msgs: 1, out_msgs: 1, in_bytes: 10, out_bytes: 10 },
];

export const jetstream: JetStreamSummary = {
  streams: [
    { name: 'ABI_JOBS_zen', subjects: ['abi.jobs.zen.>'], messages: 4, bytes: 900, first_seq: 1, last_seq: 4, consumer_count: 1, kind: 'jobs',
      consumers: [{ name: 'job-a-b', filter_subject: 'abi.jobs.zen.trigger.a.b', pending: 1, ack_pending: 0, redelivered: 0, waiting: 0 }] },
    { name: 'KV_ABI_DISCOVERY_zen', subjects: ['$KV.ABI_DISCOVERY_zen.>'], messages: 1, bytes: 300, first_seq: 1, last_seq: 1, consumer_count: 0, kind: 'kv', consumers: [] },
  ],
  memory_bytes: 0, storage_bytes: 1200, api_requests: 30, api_errors: 0, consumers: 1, messages: 5,
};
