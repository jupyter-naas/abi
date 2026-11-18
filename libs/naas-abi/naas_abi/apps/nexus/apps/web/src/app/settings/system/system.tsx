'use client';

import { Suspense, useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import type { Loaded } from './system-api';
import { useSharedJobFailures } from './jobs/failures';
import { SystemFrame, SystemRefresh } from './system-frame';
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
import { plural } from './data/data-model';

const POLL_MS = 10_000;

function Loading() {
  return <p className="system-empty">Loading…</p>;
}

// The heavier views load on first open: importing them all up front made the
// route thousands of modules, slow to compile in dev and to load and leave.
const JobsTab = dynamic(() => import('./jobs/jobs').then((m) => m.JobsTab), { ssr: false, loading: Loading });
const AgentsTab = dynamic(() => import('./agents/agents').then((m) => m.AgentsTab), { ssr: false, loading: Loading });
const TracesTab = dynamic(() => import('./traces/traces').then((m) => m.TracesTab), { ssr: false, loading: Loading });
const SystemModules = dynamic(() => import('./system-modules').then((m) => m.SystemModules), { ssr: false, loading: Loading });
const SystemNats = dynamic(() => import('./system-nats').then((m) => m.SystemNats), { ssr: false, loading: Loading });
const SystemTraffic = dynamic(() => import('./system-traffic').then((m) => m.SystemTraffic), { ssr: false, loading: Loading });
const EventsView = dynamic(() => import('./events/events-view').then((m) => m.EventsView), { ssr: false, loading: Loading });

// Views that lay out their own panes edge to edge (no padding, no page scroll).
const OWN_REFRESH: SystemView[] = ['events', 'traffic', 'jobs', 'agents', 'traces'];
const FLUSH: readonly SystemView[] = ['jobs', 'agents', 'traces', 'events'];

function Failed({ state }: { state: Extract<Loaded<unknown>, { ok: false }> }) {
  return <SourceNote label={state.status === 403 ? 'Access' : 'This view'} reason={state.reason} />;
}

function View<T>({ state, render }: { state: Loaded<T> | null; render: (data: T) => React.ReactNode }) {
  if (state === null) return <Loading />;
  return state.ok ? <>{render(state.data)}</> : <Failed state={state} />;
}

function SystemViewBody({ view }: { view: SystemView }) {
  const [nonce, setNonce] = useState(0);
  const [jobCount, setJobCount] = useState<number | null>(null);
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
      // A count, as on Users and Organizations; failed runs are the Jobs page's own banner.
      badge={view === 'jobs' && jobCount !== null ? plural(jobCount, 'job', 'jobs') : undefined}
      actions={
        // Events and Live traffic stream; Jobs, Agents and Traces have their own refresh.
        OWN_REFRESH.includes(view) ? undefined : <SystemRefresh onClick={refresh} />
      }
      flush={FLUSH.includes(view)}
    >
      {view === 'overview' && <View state={overview} render={(data) => <SystemOverview overview={data} />} />}
      {view === 'services' && <View state={services} render={(data) => <SystemServices view={data} />} />}
      {view === 'jobs' && (
        <JobsTab nonce={nonce} failures={failures} onFailuresSeen={markSeen} onJobCount={setJobCount} />
      )}
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

/** One System or Activity page: kernel services, modules, jobs, the NATS network and
 *  what happens on them. The Platform Settings shell shows it to whoever holds nexus:ReadSystem. */
export function SystemPage({ view }: { view: SystemView }) {
  return (
    <Suspense fallback={<Loading />}>
      <SystemViewBody view={view} />
    </Suspense>
  );
}
