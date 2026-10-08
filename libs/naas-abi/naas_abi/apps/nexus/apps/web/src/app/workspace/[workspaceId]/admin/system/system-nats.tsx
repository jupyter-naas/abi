'use client';

import { Fragment, useState } from 'react';
import type { Loaded } from './system-api';
import { formatBytes, formatCount, sourceLabel } from './system-format';
import type { JetStreamSummary, NatsConnection, NatsServer } from './system-types';
import { Kpi, RowToggle, Section, SourceNote, toggled } from './system-ui';

type Resource<T> = Loaded<T> | null;

function Unavailable({ state }: { state: Exclude<Resource<unknown>, null | { ok: true }> }) {
  return <SourceNote label={sourceLabel(state.source ?? 'nats_monitor')} reason={state.reason} />;
}

function Loading() {
  return <p className="system-empty">Loading…</p>;
}

function ServerSummary({ server }: { server: NatsServer }) {
  return (
    <div className="system-kpis">
      <Kpi label="Version" value={server.version} hint={server.server_name || server.server_id} />
      <Kpi label="Uptime" value={server.uptime} />
      <Kpi label="Connections" value={formatCount(server.connections)} hint={`${formatCount(server.total_connections)} since start`} />
      <Kpi label="Subscriptions" value={formatCount(server.subscriptions)} />
      <Kpi label="Messages in / out" value={`${formatCount(server.in_msgs)} / ${formatCount(server.out_msgs)}`} />
      <Kpi label="Bytes in / out" value={`${formatBytes(server.in_bytes)} / ${formatBytes(server.out_bytes)}`} />
      <Kpi label="Memory / CPU" value={`${formatBytes(server.mem_bytes)} / ${server.cpu_percent}%`} />
      <Kpi label="Slow consumers" value={formatCount(server.slow_consumers)} />
      <Kpi label="Max payload" value={formatBytes(server.max_payload)} hint={server.jetstream ? 'JetStream on' : 'JetStream off'} />
    </div>
  );
}

function Connections({ connections }: { connections: NatsConnection[] }) {
  return (
    <div className="system-table-wrap">
      <table className="system-table">
        <thead>
          <tr>
            <th className="system-num">CID</th>
            <th>Name</th>
            <th>Address</th>
            <th>Client</th>
            <th>Uptime</th>
            <th>RTT</th>
            <th className="system-num">Subs</th>
            <th className="system-num">Msgs in / out</th>
            <th className="system-num">Bytes in / out</th>
            <th className="system-num">Pending</th>
          </tr>
        </thead>
        <tbody>
          {connections.map((c) => (
            <tr key={c.cid} className="system-table-row" data-connection={c.cid}>
              <td className="system-num">{c.cid}</td>
              <td className={c.name ? 'system-mono' : 'system-empty-cell'}>{c.name || '(unnamed)'}</td>
              <td className="system-mono">{c.ip}:{c.port}</td>
              <td>{c.lang} {c.version}</td>
              <td>{c.uptime}</td>
              <td>{c.rtt || '–'}</td>
              <td className="system-num">{formatCount(c.subscriptions)}</td>
              <td className="system-num">{formatCount(c.in_msgs)} / {formatCount(c.out_msgs)}</td>
              <td className="system-num">{formatBytes(c.in_bytes)} / {formatBytes(c.out_bytes)}</td>
              <td className="system-num">{formatBytes(c.pending_bytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JetStream({ summary }: { summary: JetStreamSummary }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  return (
    <>
      <div className="system-kpis">
        <Kpi label="Streams" value={summary.streams.length} />
        <Kpi label="Consumers" value={summary.consumers} />
        <Kpi label="Messages" value={formatCount(summary.messages)} />
        <Kpi label="Storage" value={formatBytes(summary.storage_bytes)} hint={`${formatBytes(summary.memory_bytes)} in memory`} />
        <Kpi label="API requests" value={formatCount(summary.api_requests)} hint={`${formatCount(summary.api_errors)} errors`} />
      </div>
      <div className="system-table-wrap">
        <table className="system-table">
          <thead>
            <tr>
              <th>Stream</th>
              <th>Kind</th>
              <th>Subjects</th>
              <th className="system-num">Messages</th>
              <th className="system-num">Bytes</th>
              <th className="system-num">Seq</th>
              <th className="system-num">Consumers</th>
            </tr>
          </thead>
          <tbody>
            {summary.streams.map((stream) => {
              const isOpen = open.has(stream.name);
              return (
                <Fragment key={stream.name}>
                  <tr className="system-table-row" data-stream={stream.name}>
                    <td>
                      <RowToggle
                        open={isOpen}
                        disabled={!stream.consumers.length}
                        onToggle={() => setOpen((s) => toggled(s, stream.name))}
                      >
                        {stream.name}
                      </RowToggle>
                    </td>
                    <td><span className="system-chip system-chip-muted">{stream.kind}</span></td>
                    <td className="system-mono">{stream.subjects.join(', ')}</td>
                    <td className="system-num">{formatCount(stream.messages)}</td>
                    <td className="system-num">{formatBytes(stream.bytes)}</td>
                    <td className="system-num">{stream.first_seq}–{stream.last_seq}</td>
                    <td className="system-num">{stream.consumer_count}</td>
                  </tr>
                  {isOpen && (
                    <tr className="system-table-detail">
                      <td colSpan={7}>
                        <table className="system-table system-table-nested">
                          <thead>
                            <tr>
                              <th>Consumer</th>
                              <th>Filter</th>
                              <th className="system-num">Pending</th>
                              <th className="system-num">Ack pending</th>
                              <th className="system-num">Redelivered</th>
                              <th className="system-num">Waiting</th>
                            </tr>
                          </thead>
                          <tbody>
                            {stream.consumers.map((consumer) => (
                              <tr key={consumer.name}>
                                <td className="system-mono">{consumer.name}</td>
                                <td className="system-mono">{consumer.filter_subject || '–'}</td>
                                <td className="system-num">{formatCount(consumer.pending)}</td>
                                <td className="system-num">{formatCount(consumer.ack_pending)}</td>
                                <td className="system-num">{formatCount(consumer.redelivered)}</td>
                                <td className="system-num">{formatCount(consumer.waiting)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** The broker as its HTTP monitoring endpoint sees it: server, connections, JetStream. */
export function SystemNats({
  server,
  connections,
  jetstream,
}: {
  server: Resource<NatsServer>;
  connections: Resource<NatsConnection[]>;
  jetstream: Resource<JetStreamSummary>;
}) {
  return (
    <div className="system-tab-body">
      <Section title="Server" subtitle="From the broker's monitoring endpoint (/varz).">
        {server === null ? <Loading /> : server.ok ? <ServerSummary server={server.data} /> : <Unavailable state={server} />}
      </Section>
      <Section title="Connections" subtitle="Every client connected to the broker (/connz).">
        {connections === null ? (
          <Loading />
        ) : connections.ok ? (
          <Connections connections={connections.data} />
        ) : (
          <Unavailable state={connections} />
        )}
      </Section>
      <Section title="JetStream" subtitle="Streams and their consumers (/jsz): discovery KV, jobs, bus.">
        {jetstream === null ? <Loading /> : jetstream.ok ? <JetStream summary={jetstream.data} /> : <Unavailable state={jetstream} />}
      </Section>
    </div>
  );
}
