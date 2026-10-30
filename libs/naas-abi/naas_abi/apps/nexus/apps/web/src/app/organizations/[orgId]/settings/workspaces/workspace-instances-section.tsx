'use client';

import { useEffect, useMemo, useState } from 'react';
import { Package, Search } from 'lucide-react';
import { SettingsSection } from '@/components/settings/settings-ui';
import { authFetch } from '@/stores/auth';

export type CatalogOption = { id: string; label: string; kind: string };

export type InstanceCatalog = {
  agents: CatalogOption[];
  apps: CatalogOption[];
  ontologies: CatalogOption[];
  map_feeds: CatalogOption[];
  basemaps: CatalogOption[];
};

export type CatalogSeedDraft = {
  default_agent?: string;
  agents?: string[];
  apps?: string[];
  ontologies?: string[];
  maps?: { feeds?: string[]; basemaps?: { custom?: string[] } };
};

function matchesInstanceQuery(option: CatalogOption, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    option.label.toLowerCase().includes(q) ||
    option.id.toLowerCase().includes(q) ||
    option.kind.toLowerCase().includes(q)
  );
}

function InstanceChecklist({
  title,
  options,
  selected,
  onChange,
  disabled,
  searchPlaceholder,
}: {
  title: string;
  options: CatalogOption[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  disabled?: boolean;
  searchPlaceholder?: string;
}) {
  const [query, setQuery] = useState('');
  const visible = useMemo(
    () => options.filter((option) => matchesInstanceQuery(option, query)),
    [options, query]
  );
  const q = query.trim();
  const searchLabel = `Search ${title.toLowerCase()}`;

  if (!options.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No {title.toLowerCase()} in the deployment catalog.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-foreground">
        {title}
        {q && (
          <span className="ml-2 font-normal text-muted-foreground">
            ({visible.length} of {options.length})
          </span>
        )}
      </p>
      <div className="flex items-center gap-2 rounded border border-border bg-background px-3 py-2">
        <Search size={14} className="shrink-0 text-muted-foreground opacity-70" aria-hidden />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={searchPlaceholder ?? `Search ${title.toLowerCase()}…`}
          disabled={disabled}
          aria-label={searchLabel}
          className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
      </div>
      <div className="max-h-48 space-y-1 overflow-y-auto rounded border border-border p-2">
        {visible.length === 0 && q ? (
          <p className="px-1 py-2 text-sm text-muted-foreground">No matching {title.toLowerCase()}.</p>
        ) : null}
        {visible.map((option) => {
          const checked = selected.has(option.id);
          return (
            <label
              key={option.id}
              className="flex cursor-pointer items-start gap-2 text-sm text-foreground"
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={() => {
                  const next = new Set(selected);
                  if (checked) next.delete(option.id);
                  else next.add(option.id);
                  onChange(next);
                }}
              />
              <span className="break-all">{option.label}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

export function WorkspaceInstancesSection({
  orgId,
  draft,
  onDraftChange,
  disabled,
}: {
  orgId: string;
  draft: CatalogSeedDraft;
  onDraftChange: (draft: CatalogSeedDraft) => void;
  disabled?: boolean;
}) {
  const [catalog, setCatalog] = useState<InstanceCatalog | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void authFetch(`/api/organizations/${orgId}/workspace-seed-catalog`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setFailed(true);
          return;
        }
        setCatalog(await res.json());
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const agentSet = useMemo(() => new Set(draft.agents || []), [draft.agents]);
  const appSet = useMemo(() => new Set(draft.apps || []), [draft.apps]);
  const ontologySet = useMemo(() => new Set(draft.ontologies || []), [draft.ontologies]);
  const mapFeedSet = useMemo(
    () => new Set(draft.maps?.feeds || []),
    [draft.maps?.feeds]
  );
  const basemapSet = useMemo(
    () => new Set(draft.maps?.basemaps?.custom || []),
    [draft.maps?.basemaps?.custom]
  );

  const defaultAgentOptions = useMemo(
    () => (draft.agents?.length ? draft.agents : []),
    [draft.agents]
  );

  return (
    <SettingsSection
      title={
        <span className="flex items-center gap-2">
          <Package size={16} className="text-muted-foreground" />
          Instances
        </span>
      }
      description="Optional roster beyond platform defaults. Office agents still follow enabled features at sync; pick client agents, apps, ontologies and map layers here."
    >
      {failed ? (
        <p className="text-sm text-muted-foreground">
          Could not load the instance catalog. You can add instances later via config or settings.
        </p>
      ) : !catalog ? (
        <p className="text-sm text-muted-foreground">Loading instance catalog…</p>
      ) : (
        <div className="space-y-6">
          <InstanceChecklist
            title="Agents"
            options={catalog.agents}
            selected={agentSet}
            disabled={disabled}
            onChange={(next) =>
              onDraftChange({
                ...draft,
                agents: [...next],
                default_agent:
                  draft.default_agent && next.has(draft.default_agent)
                    ? draft.default_agent
                    : [...next][0],
              })
            }
          />
          {defaultAgentOptions.length > 0 && (
            <div className="account-profile-field">
              <label className="account-profile-field-label" htmlFor="default-agent">
                Default chat agent
              </label>
              <select
                id="default-agent"
                className="account-profile-field-input"
                disabled={disabled}
                value={draft.default_agent || defaultAgentOptions[0]}
                onChange={(event) =>
                  onDraftChange({ ...draft, default_agent: event.target.value })
                }
              >
                {defaultAgentOptions.map((ref) => (
                  <option key={ref} value={ref}>
                    {ref}
                  </option>
                ))}
              </select>
            </div>
          )}
          <InstanceChecklist
            title="Apps"
            options={catalog.apps}
            selected={appSet}
            disabled={disabled}
            onChange={(next) => onDraftChange({ ...draft, apps: [...next] })}
          />
          <InstanceChecklist
            title="Ontologies"
            options={catalog.ontologies}
            selected={ontologySet}
            disabled={disabled}
            onChange={(next) => onDraftChange({ ...draft, ontologies: [...next] })}
          />
          <InstanceChecklist
            title="Map feeds"
            options={catalog.map_feeds}
            selected={mapFeedSet}
            disabled={disabled}
            onChange={(next) =>
              onDraftChange({
                ...draft,
                maps: {
                  ...draft.maps,
                  feeds: [...next],
                  basemaps: draft.maps?.basemaps,
                },
              })
            }
          />
          <InstanceChecklist
            title="Basemaps"
            options={catalog.basemaps}
            selected={basemapSet}
            disabled={disabled}
            onChange={(next) =>
              onDraftChange({
                ...draft,
                maps: {
                  feeds: draft.maps?.feeds,
                  basemaps: { custom: [...next] },
                },
              })
            }
          />
        </div>
      )}
    </SettingsSection>
  );
}

export function catalogSeedPayload(draft: CatalogSeedDraft): CatalogSeedDraft | null {
  const hasAgents = (draft.agents?.length ?? 0) > 0;
  const hasApps = (draft.apps?.length ?? 0) > 0;
  const hasOntologies = (draft.ontologies?.length ?? 0) > 0;
  const hasMaps =
    (draft.maps?.feeds?.length ?? 0) > 0 || (draft.maps?.basemaps?.custom?.length ?? 0) > 0;
  if (!hasAgents && !hasApps && !hasOntologies && !hasMaps) return null;
  return {
    ...(hasAgents
      ? {
          agents: draft.agents,
          default_agent: draft.default_agent || draft.agents?.[0],
        }
      : {}),
    ...(hasApps ? { apps: draft.apps } : {}),
    ...(hasOntologies ? { ontologies: draft.ontologies } : {}),
    ...(hasMaps ? { maps: draft.maps } : {}),
  };
}
