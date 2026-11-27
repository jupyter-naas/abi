'use client';

import { useEffect, useState } from 'react';
import { FileCog } from 'lucide-react';
import { EmptyState } from '@/components/ui/empty-state';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';
import { authFetch } from '@/stores/auth';

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
 * Config preseeding (Settings > General, admins): what the deployment config loads into the
 * workspace. The seeds are owned by ``nexus_config.organizations[].workspaces[]`` in the config
 * and follow it after an API restart. The modules it offers are Access › Modules.
 */
export function WorkspaceConfiguration({ workspaceId }: { workspaceId: string }) {
  const [config, setConfig] = useState<WorkspaceConfiguration | null>(null);
  const [error, setError] = useState('');

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
