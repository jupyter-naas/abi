'use client';

import './data/data.css';

import { Fragment, useMemo, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { createDataApi, type DataApi } from './data/data-api';
import type { ResourceEntry } from './data/data-types';
import { DeleteDialog } from './data/dialogs';
import { formatExpiry } from './system-format';
import { groupRemoteModules, moduleTone } from './system-model';
import type { ModulesView } from './system-types';
import { Chips, JobList, RowToggle, Section, SourceNotes, Status, toggled } from './system-ui';

/** A discovery instance as the Data tab names it (``<module>/<instance>``). */
function instanceEntry(moduleId: string, instanceId: string): ResourceEntry {
  return {
    id: `${moduleId}/${instanceId}`,
    name: instanceId,
    kind: 'item',
    actions: ['read', 'delete'],
    size: null,
    modified: null,
    attributes: {},
  };
}

/** Modules loaded in the engine, and module instances registered in NATS discovery.
 * An instance can be evicted (crashed or stuck registrations): typed confirmation,
 * audited by the API like a Data tab delete. */
export function SystemModules({
  view,
  api: injected,
  onChanged,
}: {
  view: ModulesView;
  api?: DataApi;
  onChanged?: () => void;
}) {
  const api = useMemo(() => injected ?? createDataApi(), [injected]);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [evicting, setEvicting] = useState<ResourceEntry | null>(null);
  const groups = groupRemoteModules(view.remote);

  const evict = async (typed: string) => {
    if (!evicting) return null;
    const result = await api.remove('discovery', evicting.id, typed);
    if (!result.ok) return result;
    setEvicting(null);
    onChanged?.();
    return null;
  };

  return (
    <div className="system-tab-body">
      <Section title="Engine modules" subtitle="Loaded in the engine process this API runs in.">
        {view.engine.length === 0 ? (
          <p className="system-empty">No modules loaded.</p>
        ) : (
          <div className="system-table-wrap">
            <table className="system-table">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Name</th>
                  <th className="system-num">Agents</th>
                  <th className="system-num">Orchestrations</th>
                  <th className="system-num">Ontologies</th>
                  <th>Jobs</th>
                </tr>
              </thead>
              <tbody>
                {view.engine.map((module) => (
                  <tr key={module.module_id} className="system-table-row" data-engine-module={module.module_id}>
                    <td className="system-mono">{module.module_id}</td>
                    <td title={module.description || undefined}>{module.name || '–'}</td>
                    <td className="system-num">{module.agents}</td>
                    <td className="system-num">{module.orchestrations}</td>
                    <td className="system-num">{module.ontologies}</td>
                    <td><JobList jobs={module.jobs} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Remote modules" subtitle="Registered in NATS discovery, one row per module.">
        <SourceNotes sources={view.sources} />
        {groups.length === 0 ? (
          view.sources.discovery?.available !== false && (
            <p className="system-empty">No module instance is registered.</p>
          )
        ) : (
          <div className="system-table-wrap">
            <table className="system-table">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Instances</th>
                  <th>Version</th>
                  <th>Agents</th>
                  <th>Jobs</th>
                  <th>Next lease expiry</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const isOpen = open.has(group.module_id);
                  return (
                    <Fragment key={group.module_id}>
                      <tr className="system-table-row" data-remote-module={group.module_id}>
                        <td>
                          <RowToggle open={isOpen} onToggle={() => setOpen((s) => toggled(s, group.module_id))}>
                            {group.module_id}
                          </RowToggle>
                        </td>
                        <td>
                          <span className="system-chips">
                            {Object.entries(group.statuses).map(([status, count]) => (
                              <Status key={status} tone={moduleTone(status)} label={`${count} ${status}`} />
                            ))}
                          </span>
                        </td>
                        <td className="system-mono">{group.versions.join(', ')}</td>
                        <td><Chips values={group.agents} /></td>
                        <td><JobList jobs={group.jobs} /></td>
                        <td>{formatExpiry(group.soonestExpiry)}</td>
                      </tr>
                      {isOpen && (
                        <tr className="system-table-detail">
                          <td colSpan={6}>
                            <table className="system-table system-table-nested">
                              <thead>
                                <tr>
                                  <th>Instance</th>
                                  <th>Status</th>
                                  <th>Version</th>
                                  <th>Contract</th>
                                  <th>Lease expiry</th>
                                  <th aria-label="Actions" />
                                </tr>
                              </thead>
                              <tbody>
                                {group.instances.map((instance) => (
                                  <tr key={instance.instance_id}>
                                    <td className="system-mono">{instance.instance_id}</td>
                                    <td><Status tone={moduleTone(instance.status)} label={instance.status} /></td>
                                    <td className="system-mono">{instance.package_version}</td>
                                    <td>v{instance.contract_major}</td>
                                    <td>{formatExpiry(instance.expires_at)}</td>
                                    <td className="system-num">
                                      <button
                                        type="button"
                                        className="data-button data-button-danger-ghost"
                                        aria-label={`Evict ${instance.instance_id}`}
                                        title="Remove this registration (crashed or stuck instances)"
                                        onClick={() => setEvicting(instanceEntry(group.module_id, instance.instance_id))}
                                      >
                                        <Trash2 size={13} aria-hidden="true" /> Evict
                                      </button>
                                    </td>
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
        )}
      </Section>
      {evicting && (
        <DeleteDialog
          entry={evicting}
          noun="instance"
          verb="Evict"
          warning="Its registration is removed from discovery. A live process registers again under the same instance id on its next heartbeat, so evicting is for crashed or stuck registrations; runs it owns are not stopped."
          onConfirm={evict}
          onClose={() => setEvicting(null)}
        />
      )}
    </div>
  );
}
