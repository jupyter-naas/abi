'use client';

import { formatCount, sourceLabel } from './system-format';
import type { Overview } from './system-types';
import { Kpi, Section, StatusDot } from './system-ui';

export function SystemOverview({ overview }: { overview: Overview }) {
  const remoteTotal = Object.values(overview.remote_modules).reduce((n, c) => n + c, 0);
  const ready = overview.remote_modules.READY ?? 0;
  const server = overview.server;

  return (
    <div className="system-tab-body">
      <Section title="At a glance">
        <div className="system-kpis">
          <Kpi
            label="Kernel services serving"
            value={`${overview.serving_services} / ${overview.kernel_services}`}
            hint={`${overview.service_instances} NATS instances`}
          />
          <Kpi label="Requests served" value={formatCount(overview.requests)} hint="since each instance started" />
          <Kpi label="Engine modules" value={overview.engine_modules} />
          <Kpi label="Remote modules" value={remoteTotal} hint={`${ready} ready of ${remoteTotal}`} />
          <Kpi
            label="NATS"
            value={server ? server.version : '–'}
            hint={server ? `${server.connections} connections · up ${server.uptime}` : 'monitoring unavailable'}
          />
          <Kpi
            label="Tracing"
            value={overview.telemetry?.enabled ? 'On' : 'Off'}
            hint={
              overview.telemetry?.enabled ? (
                <>
                  {overview.telemetry.service_name}
                  {overview.telemetry.ui_url && (
                    <>
                      {' · '}
                      <a className="system-link" data-trace-ui href={overview.telemetry.ui_url} target="_blank" rel="noreferrer">
                        Open Jaeger
                      </a>
                    </>
                  )}
                </>
              ) : (
                'telemetry.enabled is off'
              )
            }
          />
          <Kpi
            label="JetStream"
            value={`${overview.jetstream_streams} streams`}
            hint={`${overview.jetstream_consumers} consumers · ${formatCount(overview.jetstream_messages)} messages`}
          />
        </div>
      </Section>
      <Section title="Sources" subtitle="Where this dashboard reads from.">
        <ul className="system-sources">
          {Object.entries(overview.sources).map(([source, status]) => (
            <li key={source} className="system-source-row" data-source={source}>
              <StatusDot tone={status.available ? 'ok' : 'error'} />
              <span className="system-source-name">{sourceLabel(source)}</span>
              <span className="system-source-reason">{status.available ? 'Reachable' : status.reason}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
