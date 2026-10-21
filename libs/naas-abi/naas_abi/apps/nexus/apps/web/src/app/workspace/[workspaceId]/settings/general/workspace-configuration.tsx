'use client';

import { useEffect, useState } from 'react';
import { FileCog, SlidersHorizontal } from 'lucide-react';
import {
  SettingsEmpty,
  SettingsNotice,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { authFetch } from '@/stores/auth';
import { featureLabel } from '@/app/organizations/[orgId]/settings/lib/feature-labels';

interface SeedRow {
  kind: string;
  value: string;
  /** Config path, e.g. nexus_config.organizations[acme].workspaces[ops].agents[0]. */
  source: string;
}

interface WorkspaceConfiguration {
  features: string[];
  pinned: string[];
  feature_overrides: Record<string, boolean>;
  feature_overrides_source: 'database' | 'deployment' | null;
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

const OVERRIDES_SOURCE_TEXT: Record<string, string> = {
  database: 'Overrides saved in Organization Settings > Workspaces.',
  deployment: 'Overrides from the deployment config.',
};

/**
 * Read-only Features and Config preseeding (Settings > General, admins). The
 * features are changed from Organization Settings > Workspaces; the seeds are
 * owned by ``nexus_config.organizations[].workspaces[]`` in the config and
 * follow it after an API restart.
 */
export function WorkspaceConfiguration({ workspaceId }: { workspaceId: string }) {
  const [config, setConfig] = useState<WorkspaceConfiguration | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setConfig(null);
    setError('');
    void authFetch(`/api/workspaces/${workspaceId}/configuration`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setError(`Could not load the workspace configuration (HTTP ${res.status}).`);
          return;
        }
        setConfig(await res.json());
      })
      .catch(() => {
        if (!cancelled) setError('Could not load the workspace configuration.');
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const overrides = Object.entries(config?.feature_overrides ?? {});

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
        description="What this workspace exposes: the role defaults plus its overrides. Change them from Organization Settings > Workspaces > Features."
      >
        {!config ? (
          !error && <p className="text-sm text-muted-foreground">Loading features...</p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {config.features.length === 0 ? (
                <span className="text-sm text-muted-foreground">No features.</span>
              ) : (
                config.features.map((feature) => (
                  <span
                    key={feature}
                    className="border border-border px-2 py-0.5 text-xs text-foreground"
                  >
                    {featureLabel(feature)}
                    {config.pinned.includes(feature) && (
                      <span className="text-muted-foreground"> · role defaults only</span>
                    )}
                  </span>
                ))
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {overrides.length
                ? `${OVERRIDES_SOURCE_TEXT[config.feature_overrides_source ?? ''] ?? ''} ${overrides
                    .map(([key, on]) => `${featureLabel(key)} ${on ? 'on' : 'off'}`)
                    .join(', ')}.`
                : 'No overrides: every feature follows the role defaults.'}
            </p>
          </div>
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
