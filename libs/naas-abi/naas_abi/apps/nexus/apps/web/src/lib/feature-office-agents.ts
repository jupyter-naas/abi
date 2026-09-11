import { getFeatureForWorkspacePath, type FeatureKey } from '@/lib/feature-access';

export type FeatureOfficeAgentSpec = {
  /** Python class `name` (what the agent picker shows). */
  name: string;
  /** Python class, matched as `…/<className>` inside a naas_abi module. */
  className: string;
};

/**
 * Feature section → office agent that binds the right chat pane there.
 *
 * Home and Chat have no row: they use the workspace default (Abi when the
 * workspace has none, see pickWorkspaceDefaultAgent). Keep in sync with
 * FEATURE_AGENTS in naas_abi/agents/feature/registry.py (a Python test checks
 * both sides). An agent only binds when the workspace roster lists it;
 * otherwise the pane keeps the workspace default.
 */
export const FEATURE_OFFICE_AGENTS: Partial<Record<FeatureKey, FeatureOfficeAgentSpec>> = {
  slides: { name: 'Slides', className: 'SlidesAgent' },
  apps: { name: 'Apps', className: 'AppsAgent' },
  marketplace: { name: 'Marketplace', className: 'MarketplaceAgent' },
  ontology: { name: 'Ontology', className: 'OntologyAgent' },
  graph: { name: 'Knowledge Graph', className: 'KnowledgeGraphAgent' },
  files: { name: 'Files', className: 'FilesAgent' },
  datasets: { name: 'Datasets', className: 'DatasetsAgent' },
  search: { name: 'Search', className: 'SearchAgent' },
  maps: { name: 'Maps', className: 'MapsAgent' },
  code: { name: 'Code', className: 'CodeAgent' },
  settings: { name: 'Settings', className: 'SettingsAgent' },
  'settings.workspace': { name: 'Settings', className: 'SettingsAgent' },
  'settings.organization': { name: 'Settings', className: 'SettingsAgent' },
  agents: { name: 'Agent Catalog', className: 'AgentCatalogAgent' },
  skills: { name: 'Agent Catalog', className: 'AgentCatalogAgent' },
};

type OfficeAgentLike = { name?: string; class_name?: string | null };

/** True for the Nexus agent of `feature`, not a lookalike from another module. */
export function isFeatureOfficeAgent(agent: OfficeAgentLike, feature: FeatureKey): boolean {
  const spec = FEATURE_OFFICE_AGENTS[feature];
  if (!spec) return false;
  if (agent.name === spec.name) return true;
  const className = agent.class_name ?? '';
  return className.endsWith(`/${spec.className}`) && className.includes('naas_abi');
}

/** True for the naas_abi Abi orchestrator, not an AbiAgent from another module. */
export function isNexusAbiAgent(agent: OfficeAgentLike): boolean {
  const className = agent.class_name ?? '';
  return className.endsWith('/AbiAgent') && className.startsWith('naas_abi.');
}

function workspaceSegments(pathname: string): string[] {
  const parts = pathname.split(/[?#]/)[0].split('/').filter(Boolean);
  const workspaceIndex = parts.indexOf('workspace');
  return workspaceIndex < 0 ? [] : parts.slice(workspaceIndex + 2);
}

/** The feature section of a route (null on Home and non-feature routes). */
export function getPaneSurfaceForPath(pathname: string | null | undefined): FeatureKey | null {
  return getFeatureForWorkspacePath(pathname || '');
}

/** The item a feature page has open (an app, an ontology file, a graph, ...). */
export type FeatureResource = {
  feature: FeatureKey;
  kind: string;
  id: string;
  label?: string;
};

function decode(segment: string | undefined): string {
  if (!segment) return '';
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/** Open items that live in the route itself (no page state needed). */
export function resourceFromPath(pathname: string | null | undefined): FeatureResource | null {
  const path = pathname || '';
  const feature = getFeatureForWorkspacePath(path);
  const seg = workspaceSegments(path);
  if (feature === 'datasets' && seg[1] && seg[2]) {
    return { feature, kind: 'dataset', id: `${decode(seg[1])}/${decode(seg[2])}` };
  }
  if (feature === 'maps' && seg[1]) {
    return { feature, kind: 'map_dataset', id: decode(seg[1]) };
  }
  if (feature === 'agents' && seg[2]) {
    return { feature, kind: 'agent', id: decode(seg[2]) };
  }
  if (feature === 'skills' && seg[2]) {
    return { feature, kind: 'skill', id: decode(seg[2]) };
  }
  if (feature === 'code' && seg[1] === 'r' && seg[2] && seg[3]) {
    return { feature, kind: 'repo', id: `${decode(seg[2])}/${decode(seg[3])}` };
  }
  return null;
}

/**
 * The open item on this route: what the page published for this feature,
 * else what the route names. A resource published by another feature is
 * ignored so a stale app id never rides into Ontology.
 */
export function featureOpenResource(
  pathname: string | null | undefined,
  published: FeatureResource | null,
): FeatureResource | null {
  const feature = getFeatureForWorkspacePath(pathname || '');
  if (!feature) return null;
  if (published && published.feature === feature && published.id) return published;
  return resourceFromPath(pathname);
}

export type FeatureChatContext = {
  feature: {
    key: FeatureKey;
    path: string;
    resource?: { kind: string; id: string; label?: string };
  };
};

/**
 * `context.feature` for a pane turn: where the user is and what is open.
 *
 * Null off feature routes (Home included), on Chat (the workspace
 * default's surface), and on Slides (it sends its own richer
 * `context.slides`).
 */
export function featureChatContext(
  pathname: string | null | undefined,
  published: FeatureResource | null,
): FeatureChatContext | null {
  const path = pathname || '';
  const key = getFeatureForWorkspacePath(path);
  if (!key || key === 'chat' || key === 'slides') return null;
  const open = featureOpenResource(path, published);
  const resource = open
    ? { kind: open.kind, id: open.id, ...(open.label ? { label: open.label } : {}) }
    : undefined;
  return { feature: { key, path, ...(resource ? { resource } : {}) } };
}
