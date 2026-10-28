'use client';

import './coding-environment.css';

import { Bot, LayoutTemplate, Monitor, TerminalSquare } from 'lucide-react';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { Avatar, Badge, RelativeTime, StatusPill } from '../data-ui';
import { StatusView, phaseTone } from '../viewers/status-view';
import type { ServiceView } from './types';

const ENVIRONMENTS = 'environments';

function isTemplate(entry: ResourceEntry): boolean {
  return entry.id.startsWith('templates/');
}

function AgentReadiness({ ready }: { ready: boolean }) {
  return (
    <Badge tone={ready ? 'success' : 'neutral'}>
      <Bot size={11} aria-hidden="true" /> {ready ? 'Agent ready' : 'Agent not ready'}
    </Badge>
  );
}

function Owner({ name }: { name: string | undefined }) {
  if (!name) return <span className="data-muted">No owner recorded</span>;
  return (
    <span className="data-codenv-owner">
      <Avatar name={name} />
      <span className="data-codenv-owner-name" title={name}>
        {name}
      </span>
    </span>
  );
}

function RootCard({ entry }: { entry: ResourceEntry }) {
  const count = entry.attributes.count;
  return (
    <div className="data-codenv-root">
      {count !== undefined && <p className="data-codenv-count">{count}</p>}
      <p className="data-card-summary">{entry.attributes.summary}</p>
    </div>
  );
}

function EnvironmentCard({ entry }: { entry: ResourceEntry }) {
  const a = entry.attributes;
  return (
    <div className="data-codenv-card">
      <span className="data-codenv-status">
        <AgentReadiness ready={a.ready === 'yes'} />
      </span>
      <Owner name={a.owner} />
    </div>
  );
}

function EnvironmentPreview({ detail }: { detail: ResourceDetail }) {
  const view = (detail.view ?? {}) as { phase?: string; fields?: Record<string, unknown>; created_at?: string | null };
  const a = detail.entry.attributes;
  if (isTemplate(detail.entry)) return <StatusView fields={view.fields} />;
  return (
    <div className="data-codenv-preview">
      <div className="data-codenv-hero">
        <AgentReadiness ready={a.ready === 'yes'} />
        {view.created_at && (
          <span className="data-muted">
            Created <RelativeTime iso={view.created_at} />
          </span>
        )}
      </div>
      <div className="data-codenv-owner-block">
        <span className="data-section-title">Owner</span>
        <Owner name={a.owner} />
      </div>
      <StatusView fields={view.fields} />
    </div>
  );
}

export const codingEnvironmentView: ServiceView = {
  name: 'coding_environment',
  label: 'Coding environments',
  description: 'Developer workspaces provisioned on the orchestrator, across every user, and the templates they start from.',
  icon: TerminalSquare,
  group: 'Platform',
  noun: { one: 'environment', many: 'environments' },
  entryIcon: (entry) => {
    if (entry.kind === 'container') return entry.id === ENVIRONMENTS ? Monitor : LayoutTemplate;
    return isTemplate(entry) ? LayoutTemplate : Monitor;
  },
  nounFor: (entry) => {
    if (entry.kind === 'container') return { one: 'group', many: 'groups' };
    return isTemplate(entry) ? { one: 'template', many: 'templates' } : { one: 'environment', many: 'environments' };
  },
  level: (depth, parent) => {
    if (depth === 0) {
      return {
        noun: { one: 'group', many: 'groups' },
        layout: 'cards',
        card: (entry) => <RootCard entry={entry} />,
      };
    }
    if (parent === ENVIRONMENTS) {
      return {
        noun: { one: 'environment', many: 'environments' },
        layout: 'cards',
        card: (entry) => <EnvironmentCard entry={entry} />,
        columns: [
          {
            id: 'template',
            label: 'Template',
            width: '1fr',
            render: (e) => <span className="data-mono">{e.attributes.template || '—'}</span>,
          },
          { id: 'created', label: 'Created', width: '1fr', render: (e) => <RelativeTime iso={e.modified} /> },
        ],
        emptyTitle: 'No coding environment',
        emptyText: 'Workspaces show up here once a user provisions one from a template.',
      };
    }
    return {
      noun: { one: 'template', many: 'templates' },
      columns: [
        {
          id: 'version',
          label: 'Active version',
          width: 'minmax(140px, 0.5fr)',
          render: (e) => <span className="data-mono">{e.attributes.active_version}</span>,
        },
      ],
      emptyTitle: 'No template',
      emptyText: 'The orchestrator offers no template to provision workspaces from.',
    };
  },
  summary: (entry) => (isTemplate(entry) ? undefined : entry.attributes.summary),
  badges: (entry) =>
    entry.kind === 'item' && !isTemplate(entry) ? (
      <StatusPill
        tone={phaseTone(entry.attributes.phase)}
        label={entry.attributes.phase ?? 'unknown'}
        pulse={phaseTone(entry.attributes.phase) === 'info'}
      />
    ) : isTemplate(entry) ? (
      <Badge>Read-only</Badge>
    ) : null,
  facts: (detail) =>
    isTemplate(detail.entry)
      ? [{ label: 'Active version', value: <span className="data-mono">{detail.entry.attributes.active_version}</span> }]
      : [
          { label: 'Template', value: detail.entry.attributes.template || '—' },
          { label: 'Created', value: <RelativeTime iso={detail.entry.modified} /> },
        ],
  preview: (detail) => (detail.view?.type === 'status' ? <EnvironmentPreview detail={detail} /> : null),
  deleteWarning: () =>
    'This destroys the workspace on the orchestrator: its disk, running processes and any work not pushed from it are lost.',
};
