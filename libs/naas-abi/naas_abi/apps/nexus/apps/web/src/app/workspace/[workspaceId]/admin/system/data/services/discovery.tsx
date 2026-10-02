'use client';

import './discovery.css';

import { Boxes, Hourglass, Radar, Server } from 'lucide-react';
import { formatDuration, parseJson } from '../data-model';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Badge, StatusPill, useNow, type Tone } from '../data-ui';
import { JsonTree } from '../viewers/json-tree';
import { StatusView, phaseTone } from '../viewers/status-view';
import type { ServiceView } from './types';

const WARN_SECONDS = 60;

/** Seconds until ``iso`` (negative once past). */
export function secondsLeft(iso: string | undefined, now: number): number | null {
  if (!iso) return null;
  const at = Date.parse(iso);
  return Number.isNaN(at) ? null : Math.round((at - now) / 1000);
}

export function leaseTone(seconds: number | null): Tone {
  if (seconds === null) return 'neutral';
  if (seconds <= 0) return 'danger';
  if (seconds <= WARN_SECONDS) return 'warn';
  return 'success';
}

export function leaseLabel(seconds: number | null): string {
  if (seconds === null) return '—';
  if (seconds <= 0) return `expired ${formatDuration(-seconds)} ago`;
  return `renews within ${formatDuration(seconds)}`;
}

/** The lease expiry, ticking every second: green, amber near expiry, red once expired. */
export function LeaseCountdown({ iso }: { iso: string | undefined }) {
  const now = useNow(1000);
  const seconds = secondsLeft(iso, now);
  return (
    <span className={`data-discovery-lease data-discovery-lease-${leaseTone(seconds)}`} title={iso}>
      <Hourglass size={12} aria-hidden="true" />
      {leaseLabel(seconds)}
    </span>
  );
}

/** ``"READY 2, STARTING 1"`` as (status, count) pairs. */
export function statusMix(value: string | undefined): [string, number][] {
  return (value ?? '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const cut = part.lastIndexOf(' ');
      return [part.slice(0, cut), Number(part.slice(cut + 1)) || 0] as [string, number];
    });
}

function list(value: string | undefined): string[] {
  return (value ?? '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

function Chips({ values, tone = 'neutral', max = 6 }: { values: string[]; tone?: Tone; max?: number }) {
  if (!values.length) return null;
  return (
    <span className="data-discovery-chips">
      {values.slice(0, max).map((v) => (
        <Badge key={v} tone={tone}>
          {v}
        </Badge>
      ))}
      {values.length > max && <Badge>+{values.length - max}</Badge>}
    </span>
  );
}

function ModuleCard({ entry }: { entry: ResourceEntry }) {
  const a = entry.attributes;
  return (
    <div className="data-discovery-card">
      <span className="data-discovery-pills">
        {statusMix(a.status).map(([status, count]) => (
          <StatusPill key={status} tone={phaseTone(status)} label={`${count} ${status.toLowerCase()}`} />
        ))}
      </span>
      {list(a.agents).length > 0 && (
        <span className="data-discovery-row">
          <span className="data-discovery-label">Agents</span>
          <Chips values={list(a.agents)} tone="info" />
        </span>
      )}
      {list(a.jobs).length > 0 && (
        <span className="data-discovery-row">
          <span className="data-discovery-label">Jobs</span>
          <Chips values={list(a.jobs)} />
        </span>
      )}
    </div>
  );
}

interface Job {
  name: string;
  description?: string;
  triggers?: string[];
  max_concurrency?: number;
  max_attempts?: number;
  timeout_seconds?: number | null;
}

interface Agent {
  name: string;
  description?: string;
  capabilities?: string[];
}

function DiscoveryPreview({ detail }: { detail: ResourceDetail }) {
  const view = (detail.view ?? {}) as {
    phase?: string;
    fields?: Record<string, unknown>;
    lease_expires_at?: string;
    agents?: Agent[];
    jobs?: Job[];
    dependencies?: { module_id: string; contract_major: number }[];
  };
  const descriptor = parseJson(detail.content?.text);
  const fields = { ...(view.fields ?? {}) };
  delete fields['Lease expires'];
  return (
    <div className="data-discovery-preview">
      <div className="data-discovery-head">
        {view.phase && <StatusPill tone={phaseTone(view.phase)} label={view.phase} />}
        <LeaseCountdown iso={view.lease_expires_at ?? detail.entry.attributes.lease_expires_at} />
      </div>
      <StatusView fields={fields} />
      <section className="data-section">
        <h4 className="data-section-title">Agents · {view.agents?.length ?? 0}</h4>
        {view.agents?.length ? (
          <div className="data-discovery-agents">
            {view.agents.map((agent) => (
              <div key={agent.name} className="data-discovery-agent">
                <p className="data-discovery-agent-name">{agent.name}</p>
                {agent.description && <p className="data-discovery-agent-text">{agent.description}</p>}
                <Chips values={agent.capabilities ?? []} max={4} />
              </div>
            ))}
          </div>
        ) : (
          <p className="data-muted">This instance exposes no agent.</p>
        )}
      </section>
      <section className="data-section">
        <h4 className="data-section-title">Jobs · {view.jobs?.length ?? 0}</h4>
        {view.jobs?.length ? (
          <table className="data-kv data-discovery-jobs">
            <tbody>
              {view.jobs.map((job) => (
                <tr key={job.name}>
                  <th>{job.name}</th>
                  <td>
                    <Chips values={job.triggers ?? []} />
                    <span className="data-muted">
                      {[
                        job.max_concurrency ? `×${job.max_concurrency} concurrent` : '',
                        job.max_attempts ? `${job.max_attempts} attempts` : '',
                        job.timeout_seconds ? `timeout ${formatDuration(job.timeout_seconds)}` : '',
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="data-muted">No scheduled or triggered job.</p>
        )}
      </section>
      {view.dependencies && view.dependencies.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Depends on</h4>
          <Chips values={view.dependencies.map((d) => `${d.module_id} v${d.contract_major}`)} max={20} />
        </section>
      )}
      {descriptor !== undefined && (
        <section className="data-section">
          <h4 className="data-section-title">Descriptor</h4>
          <JsonTree value={descriptor} depth={1} />
        </section>
      )}
    </div>
  );
}

export const discoveryView: ServiceView = {
  name: 'discovery',
  label: 'Discovery',
  description: 'Remote modules registered on the NATS network, their instances and leases.',
  icon: Radar,
  group: 'Streams & logs',
  noun: { one: 'instance', many: 'instances' },
  entryIcon: (entry) => (entry.kind === 'container' ? Boxes : Server),
  nounFor: (entry) =>
    entry.kind === 'container' ? { one: 'module', many: 'modules' } : { one: 'instance', many: 'instances' },
  deleteLabel: 'Evict',
  level: (depth) =>
    depth === 0
      ? {
          noun: { one: 'module', many: 'modules' },
          layout: 'cards',
          card: (entry) => <ModuleCard entry={entry} />,
          columns: [
            {
              id: 'instances',
              label: 'Instances',
              width: '80px',
              render: (e) => <span className="data-num">{e.attributes.instances ?? '—'}</span>,
            },
            { id: 'lease', label: 'Lease', width: '160px', render: (e) => <LeaseCountdown iso={e.attributes.lease_expires_at} /> },
            {
              id: 'versions',
              label: 'Version',
              width: '100px',
              render: (e) => <span className="data-mono">{e.attributes.versions || '—'}</span>,
            },
          ],
          emptyTitle: 'No module registered',
          emptyText:
            'Remote SDK modules appear here once they register with discovery on the NATS network (run_module with a discovery project).',
        }
      : {
          noun: { one: 'instance', many: 'instances' },
          columns: [
            {
              id: 'status',
              label: 'Status',
              width: '120px',
              render: (e) => <StatusPill tone={phaseTone(e.attributes.status)} label={e.attributes.status ?? 'unknown'} />,
            },
            {
              id: 'version',
              label: 'Version',
              width: '96px',
              render: (e) => <span className="data-mono">{e.attributes.version}</span>,
            },
            { id: 'lease', label: 'Lease', width: '170px', render: (e) => <LeaseCountdown iso={e.attributes.lease_expires_at} /> },
            {
              id: 'agents',
              label: 'Agents',
              width: '64px',
              align: 'end',
              render: (e) => <span className="data-num">{list(e.attributes.agents).length}</span>,
            },
            {
              id: 'jobs',
              label: 'Jobs',
              width: '56px',
              align: 'end',
              render: (e) => <span className="data-num">{list(e.attributes.jobs).length}</span>,
            },
          ],
          emptyTitle: 'No live instance',
          emptyText: 'Every instance of this module has unregistered or let its lease expire.',
        },
  summary: (entry) => entry.attributes.summary,
  facts: (detail) => [
    {
      label: 'Status',
      value: <StatusPill tone={phaseTone(detail.entry.attributes.status)} label={detail.entry.attributes.status ?? '—'} />,
    },
    { label: 'Version', value: <span className="data-mono">{detail.entry.attributes.version}</span> },
    { label: 'Lease', value: <LeaseCountdown iso={detail.entry.attributes.lease_expires_at} /> },
  ],
  preview: (detail) => (detail.view?.type === 'status' ? <DiscoveryPreview detail={detail} /> : null),
  deleteWarning: () =>
    'This evicts the registration from discovery. A module that is still alive registers again under a new instance id on its next heartbeat, so evict crashed or stuck instances.',
};
