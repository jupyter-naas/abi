'use client';

import { useEffect, useState } from 'react';
import { FileCog, Package, SlidersHorizontal } from 'lucide-react';
import {
  SettingsEmpty,
  SettingsNotice,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { authFetch } from '@/stores/auth';
import { featureLabel } from '@/lib/feature-labels';
import { useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { describeModuleResources } from '@/lib/workspace-resources';

interface SeedRow {
  kind: string;
  value: string;
  /** Config path, e.g. nexus_config.organizations[acme].workspaces[ops].agents[0]. */
  source: string;
}

interface WorkspaceConfiguration {
  organization_id: string | null;
  /** The deployment's enabled features. */
  features: string[];
  seeds: SeedRow[];
}

const SEED_KIND_LABELS: Record<string, string> = {
  default_agent: 'Default agent',
  agent: 'Agent',
  app: 'App',
  ontology: 'Ontology',
  graph_read_all: 'Graph (read all)',
  graph_read: 'Graph (read)',
  graph_write: 'Graph (write)',
  map_feed: 'Map feed',
  basemap: 'Basemap',
};

// Features by name (label), A to Z.
const byLabel = (a: string, b: string) => featureLabel(a).localeCompare(featureLabel(b));

/**
 * Features, Modules and Config preseeding (Settings > General, admins), read-only. Features are
 * the deployment's enabled ones (`/configuration`); Modules are what you may use here
 * (`/resources`: each module with the agents, apps, workflows and pipelines IAM lets you use).
 * Who may use what is decided by policies alone, on Roles & permissions: there is no workspace
 * set and no on/off switch. The seeds are owned by
 * ``nexus_config.organizations[].workspaces[]`` in the config and follow it after an API restart.
 */
export function WorkspaceConfiguration({ workspaceId }: { workspaceId: string }) {
  const [config, setConfig] = useState<WorkspaceConfiguration | null>(null);
  const [error, setError] = useState('');
  const { status: resourcesStatus, resources } = useWorkspaceResources(workspaceId);

  useEffect(() => {
    let cancelled = false;
    setConfig(null);
    setError('');
    (async () => {
      const res = await authFetch(`/api/workspaces/${workspaceId}/configuration`);
      if (!res.ok) throw new Error(`Could not load the workspace configuration (HTTP ${res.status}).`);
      return (await res.json()) as WorkspaceConfiguration;
    })()
      .then((next) => {
        if (!cancelled) setConfig(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error && err.message
              ? err.message
              : 'Could not load the workspace configuration.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const features = [...(config?.features ?? [])].sort(byLabel);

  return (
    <>
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <SlidersHorizontal size={16} className="text-muted-foreground" />
            Features
          </span>
        }
        description="The features this deployment enables. Who may use each one here is decided by policies, on Roles & permissions."
      >
        {!config ? (
          !error && <p className="text-sm text-muted-foreground">Loading features...</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {features.length === 0 ? (
              <span className="text-sm text-muted-foreground">No features.</span>
            ) : (
              features.map((feature) => (
                <span
                  key={feature}
                  className="border border-border px-2 py-0.5 text-xs text-foreground"
                >
                  {featureLabel(feature)}
                </span>
              ))
            )}
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <Package size={16} className="text-muted-foreground" />
            Modules
          </span>
        }
        description="What you may use here: each module with the agents, apps, workflows and pipelines you may use."
      >
        {resourcesStatus === 'loading' ? (
          <p className="text-sm text-muted-foreground">Loading modules...</p>
        ) : !resources ? (
          <p className="text-sm text-muted-foreground">What you may use here could not be read.</p>
        ) : resources.modules.length === 0 ? (
          <span className="text-sm text-muted-foreground">No module you may use here.</span>
        ) : (
          <ul className="workspace-general-modules">
            {resources.modules.map((entry) => (
              <li key={entry.module} className="workspace-general-modules-row">
                <span className="workspace-general-modules-name">{entry.module}</span>
                <span className="workspace-general-modules-items">{describeModuleResources(entry)}</span>
              </li>
            ))}
          </ul>
        )}
      </SettingsSection>

      <SettingsSection
        title={
          <span className="flex items-center gap-2">
            <FileCog size={16} className="text-muted-foreground" />
            Config preseeding
          </span>
        }
        description="Loaded from the deployment config on API boot. Read-only here: change the config and restart the API."
      >
        {!config ? (
          !error && <p className="text-sm text-muted-foreground">Loading seeds...</p>
        ) : config.seeds.length === 0 ? (
          <SettingsEmpty
            icon={<FileCog size={20} />}
            title="No config preseeding"
            description="The deployment config does not preload this workspace."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Seeded</th>
                  <th className="py-2 font-medium">Config path</th>
                </tr>
              </thead>
              <tbody>
                {config.seeds.map((row) => (
                  <tr key={row.source} className="border-t border-border">
                    <td className="whitespace-nowrap py-2 pr-3 text-muted-foreground">
                      {SEED_KIND_LABELS[row.kind] ?? row.kind}
                    </td>
                    <td className="break-all py-2 pr-3 font-medium text-foreground">
                      {row.value}
                    </td>
                    <td className="break-all py-2 font-mono text-xs text-muted-foreground">
                      {row.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SettingsSection>
    </>
  );
}
