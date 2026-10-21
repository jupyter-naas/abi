'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { FileCog, RotateCcw, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsNotice,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { authFetch } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { featureLabel } from '@/app/organizations/[orgId]/settings/lib/feature-labels';
import {
  choicesFromOverrides,
  configurableFeatures,
  overridesFromChoices,
  WorkspaceFeaturesTable,
  type FeatureChoice,
  type WorkspaceFeatureCatalog,
} from '@/app/organizations/[orgId]/settings/workspaces/workspace-features-table';

interface SeedRow {
  kind: string;
  value: string;
  /** Config path, e.g. nexus_config.organizations[acme].workspaces[ops].agents[0]. */
  source: string;
}

interface WorkspaceConfiguration {
  organization_id: string | null;
  /** Organization owners and admins edit the features (same rule as Organization Settings). */
  can_edit_features: boolean;
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
  database: 'Overrides saved in the app.',
  deployment: 'Overrides from the deployment config.',
};

// Features and overrides by name (label), A to Z.
const byLabel = (a: string, b: string) => featureLabel(a).localeCompare(featureLabel(b));

const sameOverrides = (a: Record<string, boolean>, b: Record<string, boolean>) =>
  Object.keys(a).length === Object.keys(b).length &&
  Object.entries(a).every(([key, on]) => b[key] === on);

/**
 * Features and Config preseeding (Settings > General, admins). Organization
 * owners and admins edit the features inline with the same table and endpoint
 * as Organization Settings > Workspaces; others see them read-only. The seeds
 * are owned by ``nexus_config.organizations[].workspaces[]`` in the config and
 * follow it after an API restart.
 */
export function WorkspaceConfiguration({ workspaceId }: { workspaceId: string }) {
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const [config, setConfig] = useState<WorkspaceConfiguration | null>(null);
  const [error, setError] = useState('');
  const [catalog, setCatalog] = useState<WorkspaceFeatureCatalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [draft, setDraft] = useState<Record<string, FeatureChoice>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const loadConfig = useCallback(async () => {
    const res = await authFetch(`/api/workspaces/${workspaceId}/configuration`);
    if (!res.ok) throw new Error(`Could not load the workspace configuration (HTTP ${res.status}).`);
    return (await res.json()) as WorkspaceConfiguration;
  }, [workspaceId]);

  useEffect(() => {
    let cancelled = false;
    setConfig(null);
    setError('');
    loadConfig()
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
  }, [loadConfig]);

  // The draft starts from the saved overrides, and again after each save.
  useEffect(() => {
    setDraft(choicesFromOverrides(config?.feature_overrides ?? {}));
  }, [config]);

  // Catalog and role defaults for the editable table (organization admins only).
  const orgId = config?.can_edit_features ? config.organization_id : null;
  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    setCatalogFailed(false);
    void authFetch(`/api/organizations/${orgId}/workspace-features`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setCatalogFailed(true);
          return;
        }
        const next = (await res.json()) as WorkspaceFeatureCatalog;
        setCatalog({ ...next, catalog: [...next.catalog].sort(byLabel) });
      })
      .catch(() => {
        if (!cancelled) setCatalogFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const editableFeatures = useMemo(() => configurableFeatures(catalog), [catalog]);
  const draftOverrides = overridesFromChoices(draft, editableFeatures);
  const dirty = config ? !sameOverrides(draftOverrides, config.feature_overrides) : false;

  /** ``null`` drops the saved overrides so the config applies again. */
  const saveFeatures = async (overrides: Record<string, boolean> | null) => {
    if (!orgId) return;
    setSaving(true);
    setSaveError('');
    try {
      const res = await authFetch(
        `/api/organizations/${orgId}/workspaces/${workspaceId}/features`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ overrides }),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(
          typeof data?.detail === 'string' ? data.detail : `Failed to save (HTTP ${res.status}).`
        );
      }
      setConfig(await loadConfig());
      // The sidebar and pages read the flags from the workspace store.
      void fetchWorkspaces();
    } catch (err) {
      setSaveError(
        err instanceof Error && err.message ? err.message : 'Failed to save the features'
      );
    } finally {
      setSaving(false);
    }
  };

  const features = [...(config?.features ?? [])].sort(byLabel);
  const overrides = Object.entries(config?.feature_overrides ?? {}).sort(([a], [b]) =>
    byLabel(a, b)
  );
  const overridesText = config
    ? overrides.length
      ? `${OVERRIDES_SOURCE_TEXT[config.feature_overrides_source ?? ''] ?? ''} ${overrides
          .map(([key, on]) => `${featureLabel(key)} ${on ? 'on' : 'off'}`)
          .join(', ')}.`
      : 'No overrides: every feature follows the role defaults.'
    : '';

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
        description={
          config?.can_edit_features
            ? 'Default follows the role defaults. On shows a feature to every role, Off hides it. Saving replaces the config overrides for this workspace.'
            : 'What this workspace exposes: the role defaults plus its overrides. Organization owners and admins change them.'
        }
        actions={
          orgId && catalog ? (
            <div className="flex items-center gap-2">
              {config?.feature_overrides_source === 'database' && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void saveFeatures(null)}
                  disabled={saving}
                >
                  <RotateCcw size={14} />
                  Use config
                </Button>
              )}
              {dirty && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDraft(choicesFromOverrides(config?.feature_overrides ?? {}))}
                  disabled={saving}
                >
                  Discard
                </Button>
              )}
              <Button
                size="sm"
                onClick={() => void saveFeatures(draftOverrides)}
                disabled={saving || !dirty}
              >
                {saving ? 'Saving...' : 'Save'}
              </Button>
            </div>
          ) : null
        }
      >
        {!config ? (
          !error && <p className="text-sm text-muted-foreground">Loading features...</p>
        ) : orgId && !catalogFailed ? (
          <div className="space-y-3">
            {saveError && <SettingsNotice tone="error">{saveError}</SettingsNotice>}
            {catalog ? (
              <WorkspaceFeaturesTable
                catalog={catalog}
                choices={draft}
                disabled={saving}
                onChange={(feature, choice) =>
                  setDraft((current) => ({ ...current, [feature]: choice }))
                }
              />
            ) : (
              <p className="text-sm text-muted-foreground">Loading features...</p>
            )}
            <p className="text-xs text-muted-foreground">{overridesText}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {catalogFailed && (
              <SettingsNotice tone="error">
                The feature catalog could not be loaded, so the features are read-only.
              </SettingsNotice>
            )}
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
                    {config.pinned.includes(feature) && (
                      <span className="text-muted-foreground"> · role defaults only</span>
                    )}
                  </span>
                ))
              )}
            </div>
            <p className="text-xs text-muted-foreground">{overridesText}</p>
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
