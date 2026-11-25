'use client';

import { useEffect, useState } from 'react';
import { FileCog, Package } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useWorkspaceResources } from '@/hooks/use-workspace-resources';
import { describeModuleResources } from '@/lib/workspace-resources';
import { FeatureAccess } from './feature-access';
import { Notice } from '@/components/ui/notice';
import { EmptyState } from '@/components/ui/empty-state';
import { Card } from '@/components/ui/card';

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

/**
 * Features, Modules and Config preseeding (Settings > General, admins). Features are who may use
 * each enabled feature here (`feature-access.tsx`: each choice a policy the API writes, so
 * policies stay the one place access is decided, on Access › Policies too); Modules are what you
 * may use here (`/resources`: each module with the agents, apps, workflows and pipelines IAM lets
 * you use), read-only. The seeds are owned by ``nexus_config.organizations[].workspaces[]`` in
 * the config and follow it after an API restart.
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

  return (
    <>
      {error && <Notice tone="error">{error}</Notice>}

      <FeatureAccess workspaceId={workspaceId} />

      <Card
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
      </Card>

      <Card
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
          <EmptyState framed
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
      </Card>
    </>
  );
}
