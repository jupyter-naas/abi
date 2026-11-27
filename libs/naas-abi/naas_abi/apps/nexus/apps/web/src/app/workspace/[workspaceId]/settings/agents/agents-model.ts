/**
 * Settings › Agents: the models each agent shows and the columns of its table (search, sort,
 * filter, export, as Settings › Users). Pure: the view is `page.tsx`.
 */
import type { Agent } from '@/stores/agents';
import type { ProviderConfig } from '@/stores/integrations';
import { enabledLabel, moduleItemKey, type ModuleItem } from '@/components/settings/module-items-model';

export type AgentProvider = Pick<ProviderConfig, 'id' | 'type' | 'enabled' | 'model'>;

/** The model ids an agent shows: those its class declares, else the one it is set to or resolves
 *  to (through its provider when it has one). `providers` are the enabled ones. */
export function agentModelIds(agent: Agent, providers: readonly AgentProvider[]): string[] {
  const declared = (agent.modelIds || []).map((id) => id.trim()).filter(Boolean);
  if (declared.length > 0) return Array.from(new Set(declared));

  let rawId: string | null = null;
  if (agent.provider === 'abi') {
    rawId = agent.modelId || agent.resolvedModelId || null;
  } else if (agent.provider) {
    const provider = providers.find((p) => p.type === agent.provider && p.enabled);
    rawId = agent.modelId || provider?.model || agent.resolvedModelId || null;
  } else if (agent.providerId) {
    const assigned = providers.find((p) => p.id === agent.providerId);
    rawId = assigned?.model || agent.modelId || agent.resolvedModelId || null;
  } else {
    rawId = agent.modelId || agent.resolvedModelId || null;
  }
  return rawId ? [rawId] : [];
}

/**
 * A row of the agents table: an agent of the roster (`agent`), or a module's agent it does not hold
 * (disabled, or not usable by the caller: `agent` null, what the catalog says of it); its models,
 * each with the name it is shown by; its module item (`item`, the Enabled checkbox), none for an
 * agent the workspace builds itself.
 */
export type AgentRow = {
  /** The agent's id, else its item's key. */
  key: string;
  agent: Agent | null;
  name: string;
  description: string;
  module: string;
  models: { id: string; label: string }[];
  item: ModuleItem | null;
};

/**
 * The module item an agent of the roster is: its class's module (the catalog's, or a package of
 * it) and its name (the agent's, or its class's). The closest module wins.
 */
export function agentItemFor(agent: Agent, items: readonly ModuleItem[]): ModuleItem | null {
  if (!agent.class_name) return null;
  const python = agentModule(agent);
  const classPart = agent.class_name.slice(python.length + 1);
  let found: ModuleItem | null = null;
  for (const item of items) {
    if (item.kind !== 'agents') continue;
    if (python !== item.module && !python.startsWith(`${item.module}.`)) continue;
    if (item.name !== agent.name && item.name !== classPart) continue;
    if (!found || item.module.length > found.module.length) found = item;
  }
  return found;
}

/** Whether the workspace builds the agent itself (no module): always enabled. */
export const builtHere = (row: AgentRow): boolean => !!row.agent && !row.agent.class_name;

/**
 * The rows of the table, A to Z by name: the roster's agents, then every module agent (`items`)
 * none of them is.
 */
export function agentRows(
  agents: readonly Agent[],
  providers: readonly AgentProvider[],
  labelOf: (modelId: string) => string,
  items: readonly ModuleItem[] = [],
): AgentRow[] {
  const matched = new Set<ModuleItem>();
  const listed: AgentRow[] = agents.map((agent) => {
    const item = agentItemFor(agent, items);
    if (item) matched.add(item);
    return {
      key: agent.id,
      agent,
      name: agent.name,
      description: agent.description,
      module: agentModule(agent),
      models: agentModelIds(agent, providers).map((id) => ({ id, label: labelOf(id) })),
      item,
    };
  });
  const unlisted: AgentRow[] = items
    .filter((item) => item.kind === 'agents' && !matched.has(item))
    .map((item) => ({
      key: moduleItemKey(item),
      agent: null,
      name: item.label,
      description: '',
      module: item.module,
      models: [],
      item,
    }));
  return [...listed, ...unlisted].sort((a, b) => a.name.localeCompare(b.name));
}

/** What the Models cell says when an agent has none: an ABI agent's model is not exposed. */
export function noModelLabel(agent: Agent): string {
  return agent.provider === 'abi' ? 'Not exposed' : 'Not assigned';
}

/** The module an agent's class comes from, as its row shows it under the name. */
export function agentModule(agent: Agent): string {
  return agent.class_name ? agent.class_name.split('/')[0] : '';
}

export type AgentColumnId = 'agent' | 'models' | 'enabled';
export const AGENT_COLUMNS: { id: AgentColumnId; label: string }[] = [
  { id: 'agent', label: 'Agent' },
  { id: 'models', label: 'Models' },
  { id: 'enabled', label: 'Enabled' },
];

/**
 * What a column filter sees of a row: the agent's name, its model names (or why it has none;
 * nothing for a module agent the roster does not hold), Enabled or Disabled.
 */
export function agentCellValues(row: AgentRow, column: AgentColumnId): string[] {
  if (column === 'agent') return [row.name];
  if (column === 'enabled') return [enabledLabel(row.item)];
  if (!row.agent) return [];
  return row.models.length === 0 ? [noModelLabel(row.agent)] : row.models.map((model) => model.label);
}

/** What the search bar reads of a row: name, description, module and models. */
export function agentSearchTexts(row: AgentRow): string[] {
  return [row.name, row.description, row.module, ...agentCellValues(row, 'models')];
}

export const AGENT_EXPORT_HEADERS = ['Agent', 'Module', 'Description', 'Models', 'Enabled'];

/** A row of the CSV / Excel export, as the table shows it. */
export function agentExportRow(row: AgentRow): string[] {
  return [
    row.name,
    row.module,
    row.description,
    agentCellValues(row, 'models').join('; '),
    enabledLabel(row.item),
  ];
}
