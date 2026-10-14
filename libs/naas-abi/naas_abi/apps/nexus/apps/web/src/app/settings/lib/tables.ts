/**
 * Tables served by `GET /api/admin/tables/{name}`, each one a Platform Settings
 * page at `/settings/<slug>`. Keep in sync with core/platform_tables.py.
 *
 * No icons or React here: src/middleware.ts imports this list.
 */
export const PLATFORM_TABLE_SECTIONS = [
  {
    label: 'People & access',
    tables: [
      'users',
      'organizations',
      'organization_members',
      'organization_role_features',
      'workspaces',
      'workspace_members',
      'workspace_resource_policies',
    ],
  },
  {
    label: 'Sign-in & security',
    tables: [
      'refresh_tokens',
      'revoked_tokens',
      'magic_link_tokens',
      'password_reset_tokens',
      'password_changes',
      'api_keys',
      'secrets',
      'rate_limit_events',
      'audit_logs',
    ],
  },
  {
    label: 'Chat, agents & models',
    tables: [
      'conversations',
      'messages',
      'chat_ingestion_jobs',
      'agent_configs',
      'skills',
      'model_catalog',
      'provider_configs',
      'inference_servers',
    ],
  },
  {
    label: 'Apps',
    tables: ['app_configs'],
  },
  {
    label: 'Code',
    tables: ['coding_environments'],
  },
  {
    label: 'Maps',
    tables: ['maps_layouts', 'maps_feed_layers', 'maps_basemaps', 'maps_grants', 'maps_settings'],
  },
  {
    label: 'Graph',
    tables: ['graph_nodes', 'graph_edges', 'graph_views'],
  },
  {
    label: 'Ontology',
    tables: ['ontologies', 'ontology_icons'],
  },
  {
    label: 'Search',
    tables: ['search_settings', 'search_topics'],
  },
] as const;

export type PlatformTableName = (typeof PLATFORM_TABLE_SECTIONS)[number]['tables'][number];

export const PLATFORM_TABLES: readonly PlatformTableName[] = PLATFORM_TABLE_SECTIONS.flatMap(
  (section) => section.tables
);

export const PLATFORM_TABLE_LABELS: Record<PlatformTableName, string> = {
  users: 'Users',
  organizations: 'Organizations',
  organization_members: 'Organization members',
  organization_role_features: 'Organization role features',
  workspaces: 'Workspaces',
  workspace_members: 'Workspace members',
  workspace_resource_policies: 'Workspace resource policies',
  refresh_tokens: 'Sessions',
  revoked_tokens: 'Revoked tokens',
  magic_link_tokens: 'Magic links',
  password_reset_tokens: 'Password resets',
  password_changes: 'Password changes',
  api_keys: 'API keys',
  secrets: 'Secrets',
  rate_limit_events: 'Rate limit events',
  audit_logs: 'Audit logs',
  conversations: 'Conversations',
  messages: 'Messages',
  chat_ingestion_jobs: 'Chat ingestion jobs',
  agent_configs: 'Agents',
  skills: 'Skills',
  model_catalog: 'Model catalog',
  provider_configs: 'Providers',
  inference_servers: 'Inference servers',
  app_configs: 'Apps',
  coding_environments: 'Coding environments',
  maps_layouts: 'Map feeds',
  maps_feed_layers: 'Map feed layers',
  maps_basemaps: 'Basemaps',
  maps_grants: 'Map grants',
  maps_settings: 'Maps settings',
  graph_nodes: 'Graph nodes',
  graph_edges: 'Graph edges',
  graph_views: 'Graph views',
  ontologies: 'Ontologies',
  ontology_icons: 'Ontology icons',
  search_settings: 'Search settings',
  search_topics: 'Search topics',
};

export function isPlatformTable(name: string): name is PlatformTableName {
  return (PLATFORM_TABLES as readonly string[]).includes(name);
}

export function platformTableLabel(name: string): string {
  return isPlatformTable(name) ? PLATFORM_TABLE_LABELS[name] : name;
}

export function platformTableSection(name: string): string | null {
  return PLATFORM_TABLE_SECTIONS.find((s) => (s.tables as readonly string[]).includes(name))?.label ?? null;
}

/**
 * Old workspace settings links (`/settings/<slug>`, from before settings moved
 * under /workspace/[id]) that the middleware still redirects to the workspace.
 * A table page never takes one of these paths. Keep in sync with SETTINGS_GROUPS
 * in components/shell/settings-nav.tsx (a test checks it).
 */
export const LEGACY_WORKSPACE_SETTINGS_SLUGS: readonly string[] = [
  'theme',
  'members',
  'servers',
  'services',
  'secrets',
  'export',
  'agents',
  'ontologies',
  'graphs',
  'search',
  'maps',
  'skills',
  'apps',
  'models',
  'drives',
];

/** URL slug of a table page: the table name, or `<name>_table` when the name is a legacy path. */
export function platformTableSlug(name: string): string {
  return LEGACY_WORKSPACE_SETTINGS_SLUGS.includes(name) ? `${name}_table` : name;
}

export const PLATFORM_TABLE_SLUGS: readonly string[] = PLATFORM_TABLES.map(platformTableSlug);

/** The table a `/settings/<slug>` page shows, or null when the slug is not a table page. */
export function platformTableFromSlug(slug: string): PlatformTableName | null {
  return PLATFORM_TABLES.find((name) => platformTableSlug(name) === slug) ?? null;
}

/** Joins primary key values into one row id; keep in sync with ROW_ID_SEPARATOR. */
export const ROW_ID_SEPARATOR = '~';

/** The id a row page uses: its primary key value(s), joined with `~`. Null without a key. */
export function platformRowId(
  row: Record<string, unknown>,
  primaryKey: readonly string[]
): string | null {
  if (primaryKey.length === 0) return null;
  return primaryKey.map((column) => String(row[column])).join(ROW_ID_SEPARATOR);
}

/** `/settings/<table slug>/<row id>`. */
export function platformRowPath(table: string, rowId: string): string {
  return `/settings/${platformTableSlug(table)}/${encodeURIComponent(rowId)}`;
}
