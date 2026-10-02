'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  SettingsFilterSelect,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';
import { buildServiceUrl, resolveServiceHost } from '@/lib/docker-services';
import { describePlatformServices, type ConfiguredService } from '@/lib/platform-services';
import { authFetch } from '@/stores/auth';
import { ServicesForbidden } from './services-forbidden';

type LoadState =
  | { status: 'loading' }
  | { status: 'forbidden' }
  | { status: 'error'; message: string }
  | { status: 'ready'; services: ConfiguredService[] };

/**
 * The platform services set in config.yaml, with their provider (adapter) and the URL
 * of the web UI that manages them. A row with a web UI opens that service's page.
 */
export default function ServicesSettingsPage() {
  const router = useRouter();
  const workspaceId = useParams()?.workspaceId as string;
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [searchQuery, setSearchQuery] = useState('');
  const [providerFilter, setProviderFilter] = useState('all');
  const [webUiFilter, setWebUiFilter] = useState('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/services');
        if (cancelled) return;
        if (res.status === 401 || res.status === 403) {
          setState({ status: 'forbidden' });
        } else if (!res.ok) {
          setState({
            status: 'error',
            message:
              res.status === 404
                ? 'The API does not list services yet. Restart ABI to load the new endpoint.'
                : `Failed to load services (HTTP ${res.status}).`,
          });
        } else {
          setState({ status: 'ready', services: await res.json() });
        }
      } catch {
        if (!cancelled) setState({ status: 'error', message: 'Failed to load services. Please try again.' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === 'loading') return <SettingsLoading />;
  if (state.status === 'forbidden') return <ServicesForbidden />;

  const host = resolveServiceHost();
  const services = describePlatformServices(state.status === 'ready' ? state.services : []).map((service) => ({
    ...service,
    url: service.webUi ? buildServiceUrl(service.webUi, host) : null,
  }));
  const providers = Array.from(new Set(services.flatMap((service) => service.adapters))).sort();
  const query = searchQuery.trim().toLowerCase();
  const filteredServices = services.filter((service) => {
    if (providerFilter !== 'all' && !service.adapters.includes(providerFilter)) return false;
    if (webUiFilter === 'yes' && !service.url) return false;
    if (webUiFilter === 'no' && service.url) return false;
    return (
      !query ||
      [service.label, service.id, service.description, service.url ?? '', ...service.adapters]
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
  });
  const servicePath = (webUiId: string) => `/workspace/${workspaceId}/settings/services/${webUiId}`;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Services"
        badge={services.length}
        description="Platform services set in config.yaml. Open a service with a web UI to manage it inside Nexus."
      />

      {state.status === 'error' && <SettingsNotice tone="error">{state.message}</SettingsNotice>}

      <div className="space-y-4">
        <SettingsTableToolbar
          search={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search services..."
          filters={
            <>
              <SettingsFilterSelect
                label="Provider"
                value={providerFilter}
                onChange={setProviderFilter}
                options={[
                  { value: 'all', label: 'All providers' },
                  ...providers.map((provider) => ({ value: provider, label: provider })),
                ]}
              />
              <SettingsFilterSelect
                label="Web UI"
                value={webUiFilter}
                onChange={setWebUiFilter}
                options={[
                  { value: 'all', label: 'All services' },
                  { value: 'yes', label: 'With web UI' },
                  { value: 'no', label: 'Without web UI' },
                ]}
              />
            </>
          }
          meta={`${countLabel(filteredServices.length, services.length, 'service')} · ${
            services.filter((service) => service.url).length
          } with a web UI`}
        />
        <div className={settingsTable.wrapper}>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Service</th>
                <th className={cn(settingsTable.th, 'w-40')}>Provider</th>
                <th className={settingsTable.th}>URL</th>
                <th className={settingsTable.th}>Description</th>
              </tr>
            </thead>
            <tbody>
              {filteredServices.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-muted-foreground">
                    {services.length === 0 ? 'No services' : 'No services match the current search and filters'}
                  </td>
                </tr>
              )}
              {filteredServices.map((service) => {
                const Icon = service.icon;
                const webUi = service.webUi;
                return (
                  <tr
                    key={service.id}
                    className={cn(settingsTable.row, webUi && 'cursor-pointer')}
                    onClick={webUi ? () => router.push(servicePath(webUi.id)) : undefined}
                    title={webUi ? `Open ${webUi.label}` : undefined}
                  >
                    <td className={settingsTable.td}>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-muted">
                          <Icon size={16} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          {webUi ? (
                            <Link
                              href={servicePath(webUi.id)}
                              onClick={(event) => event.stopPropagation()}
                              className="font-medium hover:underline"
                            >
                              {service.label}
                            </Link>
                          ) : (
                            <p className="font-medium">{service.label}</p>
                          )}
                          <p className="font-mono text-xs text-muted-foreground">{service.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className={settingsTable.td}>
                      {service.adapters.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {service.adapters.map((adapter) => (
                            <Badge key={adapter} variant="outline" className="font-mono">
                              {adapter}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className={settingsTable.td}>
                      {service.url ? (
                        <a
                          href={service.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(event) => event.stopPropagation()}
                          title={`Open ${webUi?.label} in a new tab`}
                          className="inline-flex items-center gap-1 break-all font-mono text-xs text-muted-foreground hover:text-foreground hover:underline"
                        >
                          {service.url}
                          <ExternalLink size={12} className="shrink-0" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className={cn(settingsTable.td, 'text-muted-foreground')}>{service.description}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
