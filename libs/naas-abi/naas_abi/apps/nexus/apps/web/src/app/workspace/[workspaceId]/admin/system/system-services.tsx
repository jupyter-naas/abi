'use client';

import { Fragment, useState } from 'react';
import { formatCount, formatMs } from './system-format';
import { averageLatency, serviceTone } from './system-model';
import type { KernelServiceStatus, KernelServicesView } from './system-types';
import { Chips, RowToggle, SourceNotes, Status, toggled } from './system-ui';

const STATUS_LABELS: Record<KernelServiceStatus, string> = {
  serving: 'Serving',
  silent: 'No responders',
  not_exposed: 'Not on NATS',
};

/** Kernel services: configured adapters plus live NATS micro-service stats. */
export function SystemServices({ view }: { view: KernelServicesView }) {
  const [open, setOpen] = useState<Set<string>>(new Set());

  return (
    <div className="system-tab-body">
      <SourceNotes sources={view.sources} />
      <div className="system-table-wrap">
        <table className="system-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Adapters</th>
              <th>NATS service</th>
              <th>Status</th>
              <th className="system-num">Instances</th>
              <th className="system-num">Requests</th>
              <th className="system-num">Errors</th>
              <th className="system-num">Avg latency</th>
            </tr>
          </thead>
          <tbody>
            {view.services.map((service) => {
              const isOpen = open.has(service.name);
              const requests = service.instances.reduce((n, i) => n + i.requests, 0);
              const errors = service.instances.reduce((n, i) => n + i.errors, 0);
              return (
                <Fragment key={service.name}>
                  <tr className="system-table-row" data-service={service.name}>
                    <td>
                      <RowToggle
                        open={isOpen}
                        disabled={!service.instances.length}
                        onToggle={() => setOpen((s) => toggled(s, service.name))}
                      >
                        {service.name}
                      </RowToggle>
                    </td>
                    <td><Chips values={service.adapters} /></td>
                    <td className="system-mono">{service.nats_service ?? '–'}</td>
                    <td><Status tone={serviceTone(service.status)} label={STATUS_LABELS[service.status]} /></td>
                    <td className="system-num">{service.instances.length}</td>
                    <td className="system-num">{formatCount(requests)}</td>
                    <td className="system-num">{formatCount(errors)}</td>
                    <td className="system-num">{formatMs(averageLatency(service.instances))}</td>
                  </tr>
                  {isOpen && (
                    <tr className="system-table-detail">
                      <td colSpan={8}>
                        {service.instances.map((instance) => (
                          <div key={instance.instance_id} className="system-detail-block">
                            <p className="system-detail-title">
                              <span className="system-mono">{instance.instance_id}</span>
                              <span className="system-detail-meta">
                                v{instance.version} · started {instance.started}
                              </span>
                            </p>
                            <table className="system-table system-table-nested">
                              <thead>
                                <tr>
                                  <th>Endpoint</th>
                                  <th>Subject</th>
                                  <th className="system-num">Requests</th>
                                  <th className="system-num">Errors</th>
                                  <th className="system-num">Avg</th>
                                  <th>Last error</th>
                                </tr>
                              </thead>
                              <tbody>
                                {instance.endpoints.map((endpoint) => (
                                  <tr key={endpoint.subject}>
                                    <td>{endpoint.name}</td>
                                    <td className="system-mono">{endpoint.subject}</td>
                                    <td className="system-num">{formatCount(endpoint.requests)}</td>
                                    <td className="system-num">{formatCount(endpoint.errors)}</td>
                                    <td className="system-num">{formatMs(endpoint.average_ms)}</td>
                                    <td>{endpoint.last_error || '–'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ))}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="system-footnote">
        Counters are per instance since it started. Domain errors travel in the reply body and are
        not counted here.
      </p>
    </div>
  );
}
