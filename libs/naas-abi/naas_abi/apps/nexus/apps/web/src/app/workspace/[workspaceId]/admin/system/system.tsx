'use client';

import './system.css';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { usePlatformStatusStore } from '@/stores/platform-status';
import type { Loaded } from './system-api';
import { useSuperadminAccess } from './system-access';
import { SystemModules } from './system-modules';
import { SystemNats } from './system-nats';
import { SystemOverview } from './system-overview';
import { useSystemResource } from './system-resource';
import { SystemServices } from './system-services';
import { SystemTraffic } from './system-traffic';
import { SYSTEM_TABS, parseSystemTab, type SystemTab } from './system-tabs';
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

function Failed({ state }: { state: Extract<Loaded<unknown>, { ok: false }> }) {
  return <SourceNote label={state.status === 403 ? 'Access' : 'This view'} reason={state.reason} />;
}

function View<T>({ state, render }: { state: Loaded<T> | null; render: (data: T) => React.ReactNode }) {
  if (state === null) return <Loading />;
  return state.ok ? <>{render(state.data)}</> : <Failed state={state} />;
}

function SystemApp() {
  const access = useSuperadminAccess();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab = parseSystemTab(searchParams.get('tab'));
  const [nonce, setNonce] = useState(0);
  const setRefresh = usePlatformStatusStore((s) => s.setRefresh);
  const clearRefresh = usePlatformStatusStore((s) => s.clearRefresh);

  const on = (t: SystemTab) => ({ enabled: access === 'authorized' && tab === t, intervalMs: POLL_MS, nonce });
  const overview = useSystemResource<Overview>('/overview', on('overview'));
  const services = useSystemResource<KernelServicesView>('/services', on('services'));
  const modules = useSystemResource<ModulesView>('/modules', on('modules'));
  const server = useSystemResource<NatsServer>('/nats/server', on('nats'));
  const connections = useSystemResource<NatsConnection[]>('/nats/connections', on('nats'));
  const jetstream = useSystemResource<JetStreamSummary>('/nats/jetstream', on('nats'));

  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  useEffect(() => {
    if (access !== 'authorized') return;
    setRefresh({ onRefresh: refresh, title: 'Refresh system views' });
    return () => clearRefresh();
  }, [access, refresh, setRefresh, clearRefresh]);

  const selectTab = (next: SystemTab) => {
    const params = new URLSearchParams(searchParams.toString());
    if (next === 'overview') params.delete('tab');
    else params.set('tab', next);
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  };

  if (access === 'checking') {
    return <div className="system-gate">Checking access…</div>;
  }
  if (access === 'denied') {
    return (
      <div className="system-gate">
        <h1 className="system-gate-title">Forbidden</h1>
        <p className="system-gate-text">
          Platform super admin role required. Set <code>is_superadmin: true</code> on the matching
          user in the API configuration and restart the API to grant access.
        </p>
      </div>
    );
  }

  return (
    <div className="system-page">
      <Header title="System" subtitle="Kernel services, modules and the NATS network" />
      <nav className="system-tabs" aria-label="System views">
        {SYSTEM_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={t.id === tab ? 'system-tab system-tab-active' : 'system-tab'}
            aria-current={t.id === tab ? 'page' : undefined}
            onClick={() => selectTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="system-body">
        {tab === 'overview' && <View state={overview} render={(data) => <SystemOverview overview={data} />} />}
        {tab === 'services' && <View state={services} render={(data) => <SystemServices view={data} />} />}
        {tab === 'modules' && <View state={modules} render={(data) => <SystemModules view={data} />} />}
        {tab === 'nats' && <SystemNats server={server} connections={connections} jetstream={jetstream} />}
        {tab === 'traffic' && <SystemTraffic />}
      </div>
    </div>
  );
}

/** Platform super admins: kernel services, modules and the NATS network of this deployment. */
export default function SystemPage() {
  return (
    <Suspense fallback={<div className="system-gate">Loading…</div>}>
      <SystemApp />
    </Suspense>
  );
}
