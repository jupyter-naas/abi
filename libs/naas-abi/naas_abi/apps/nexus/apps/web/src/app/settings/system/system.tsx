'use client';

import './system.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

import { Suspense, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import { RefreshCw } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import type { Loaded } from './system-api';
import { useSharedJobFailures } from './jobs/failures';
import { SystemOverview } from './system-overview';
import { useSystemResource } from './system-resource';
import { SystemServices } from './system-services';
import { SYSTEM_VIEWS, type SystemView } from './system-tabs';
import type {
  JetStreamSummary,
  KernelServicesView,
  ModulesView,
  NatsConnection,
  NatsServer,
  Overview,
} from './system-types';
import { SourceNote } from './system-ui';

const POLL_MS = 10_000;

function Loading() {
  return <p className="system-empty">Loading…</p>;
}

// The heavier views load on first open: importing them all up front made the
// route thousands of modules, slow to compile in dev and to load and leave.
const DataExplorer = dynamic(() => import('./data/explorer').then((m) => m.DataExplorer), { ssr: false, loading: Loading });
const JobsTab = dynamic(() => import('./jobs/jobs').then((m) => m.JobsTab), { ssr: false, loading: Loading });
const AgentsTab = dynamic(() => import('./agents/agents').then((m) => m.AgentsTab), { ssr: false, loading: Loading });
const TracesTab = dynamic(() => import('./traces/traces').then((m) => m.TracesTab), { ssr: false, loading: Loading });
const SystemModules = dynamic(() => import('./system-modules').then((m) => m.SystemModules), { ssr: false, loading: Loading });
const SystemNats = dynamic(() => import('./system-nats').then((m) => m.SystemNats), { ssr: false, loading: Loading });
const SystemTraffic = dynamic(() => import('./system-traffic').then((m) => m.SystemTraffic), { ssr: false, loading: Loading });
const EventsView = dynamic(() => import('./events/events-view').then((m) => m.EventsView), { ssr: false, loading: Loading });

// Views that lay out their own panes edge to edge (no padding, no page scroll).
const FLUSH: readonly SystemView[] = ['data', 'jobs', 'agents', 'traces', 'events'];

function Failed({ state }: { state: Extract<Loaded<unknown>, { ok: false }> }) {
  return <SourceNote label={state.status === 403 ? 'Access' : 'This view'} reason={state.reason} />;
}

function View<T>({ state, render }: { state: Loaded<T> | null; render: (data: T) => React.ReactNode }) {
  if (state === null) return <Loading />;
  return state.ok ? <>{render(state.data)}</> : <Failed state={state} />;
}

/**
 * A page of the Platform Settings shell that fills its height: the title, its
 * actions, then a body that scrolls (or lays out its own panes when `flush`).
 */
export function SystemFrame({
  title,
  subtitle,
  badge,
  actions,
  flush = false,
  children,
}: {
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="system-page">
      <div className="system-page-header">
        <OrgSettingsPageHeader title={title} subtitle={subtitle} badge={badge} actions={actions} />
      </div>
      <div className={flush ? 'system-body system-body-flush' : 'system-body'}>{children}</div>
    </div>
  );
}

function SystemViewBody({ view }: { view: SystemView }) {
  const [nonce, setNonce] = useState(0);
  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  const on = (v: SystemView) => ({ enabled: view === v, intervalMs: POLL_MS, nonce });
  const overview = useSystemResource<Overview>('/overview', on('overview'));
  const services = useSystemResource<KernelServicesView>('/services', on('services'));
  const modules = useSystemResource<ModulesView>('/modules', on('modules'));
  const server = useSystemResource<NatsServer>('/nats/server', on('nats'));
  const connections = useSystemResource<NatsConnection[]>('/nats/connections', on('nats'));
  const jetstream = useSystemResource<JetStreamSummary>('/nats/jetstream', on('nats'));
  // Runs that failed since the admin last looked (the shell polls them for the sidebar).
  const { failures, markSeen } = useSharedJobFailures();
  const meta = SYSTEM_VIEWS.find((v) => v.id === view) ?? SYSTEM_VIEWS[0];

  return (
    <SystemFrame
      title={meta.label}
      subtitle={meta.description}
      badge={
        view === 'jobs' && failures && failures.count > 0
          ? `${failures.more ? `${failures.count}+` : failures.count} failed since you last looked`
          : undefined
      }
      actions={
        view === 'events' || view === 'traffic' ? undefined : (
          <button type="button" className="org-settings-users-secondary-button" onClick={refresh}>
            <RefreshCw size={16} />
            Refresh
          </button>
        )
      }
      flush={FLUSH.includes(view)}
    >
      {view === 'overview' && <View state={overview} render={(data) => <SystemOverview overview={data} />} />}
      {view === 'services' && <View state={services} render={(data) => <SystemServices view={data} />} />}
      {view === 'data' && <DataExplorer nonce={nonce} />}
      {view === 'jobs' && <JobsTab nonce={nonce} failures={failures} onFailuresSeen={markSeen} />}
      {view === 'agents' && <AgentsTab nonce={nonce} />}
      {view === 'traces' && <TracesTab nonce={nonce} />}
      {view === 'modules' && (
        <View state={modules} render={(data) => <SystemModules view={data} onChanged={refresh} />} />
      )}
      {view === 'nats' && <SystemNats server={server} connections={connections} jetstream={jetstream} />}
      {view === 'traffic' && <SystemTraffic />}
      {view === 'events' && <EventsView />}
    </SystemFrame>
  );
}

/** One System page: kernel services, their data, modules and the NATS network of this
 *  deployment. The Platform Settings shell shows it to whoever holds nexus:ReadSystem. */
export function SystemPage({ view }: { view: SystemView }) {
  return (
    <Suspense fallback={<Loading />}>
      <SystemViewBody view={view} />
    </Suspense>
  );
}
