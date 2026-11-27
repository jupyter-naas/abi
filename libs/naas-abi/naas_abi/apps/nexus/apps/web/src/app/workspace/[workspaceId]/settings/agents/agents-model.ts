/**
 * Settings › Agents: the models each agent shows and the columns of its table (search, sort,
 * filter, export, as Settings › Users). Pure: the view is `page.tsx`.
 */
import type { Agent } from '@/stores/agents';
import type { ProviderConfig } from '@/stores/integrations';

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

/** A row of the agents table: the agent and its models, each with the name it is shown by. */
export type AgentRow = { agent: Agent; models: { id: string; label: string }[] };

/** The rows of the table, A to Z by name. */
export function agentRows(
  agents: readonly Agent[],
  providers: readonly AgentProvider[],
  labelOf: (modelId: string) => string,
): AgentRow[] {
  return agents
    .map((agent) => ({ agent, models: agentModelIds(agent, providers).map((id) => ({ id, label: labelOf(id) })) }))
    .sort((a, b) => a.agent.name.localeCompare(b.agent.name));
}

/** What the Models cell says when an agent has none: an ABI agent's model is not exposed. */
export function noModelLabel(agent: Agent): string {
  return agent.provider === 'abi' ? 'Not exposed' : 'Not assigned';
}

/** The module an agent's class comes from, as its row shows it under the name. */
export function agentModule(agent: Agent): string {
  return agent.class_name ? agent.class_name.split('/')[0] : '';
}

export type AgentColumnId = 'agent' | 'models';
export const AGENT_COLUMNS: { id: AgentColumnId; label: string }[] = [
  { id: 'agent', label: 'Agent' },
  { id: 'models', label: 'Models' },
];

/** What a column filter sees of a row: the agent's name, its model names (or why it has none). */
export function agentCellValues(row: AgentRow, column: AgentColumnId): string[] {
  if (column === 'agent') return [row.agent.name];
  return row.models.length === 0 ? [noModelLabel(row.agent)] : row.models.map((model) => model.label);
}

/** What the search bar reads of a row: name, description, module and models. */
export function agentSearchTexts(row: AgentRow): string[] {
  return [row.agent.name, row.agent.description, agentModule(row.agent), ...agentCellValues(row, 'models')];
}

export const AGENT_EXPORT_HEADERS = ['Agent', 'Module', 'Description', 'Models'];

/** A row of the CSV / Excel export, as the table shows it. */
export function agentExportRow(row: AgentRow): string[] {
  return [row.agent.name, agentModule(row.agent), row.agent.description, agentCellValues(row, 'models').join('; ')];
}
