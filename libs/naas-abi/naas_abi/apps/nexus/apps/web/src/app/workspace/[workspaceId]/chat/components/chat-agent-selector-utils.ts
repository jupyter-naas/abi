import type { Agent } from '@/stores/agents';
import type { CatalogModel } from '@/stores/models';
import { modelDisplayName } from '@/stores/models';
import type { ProviderConfig } from '@/stores/integrations';

const BADGE_TOKENS = [
  'Extra High',
  'High Fast',
  'High',
  'Medium',
  'Low',
  'Fast',
  'Thinking',
  'Max',
] as const;

export type ModelBadge = (typeof BADGE_TOKENS)[number];

export interface ParsedModelLabel {
  title: string;
  badges: string[];
}

/** Split display names like "Opus 5 High Fast" into title + badge chips. */
export function parseModelLabel(raw: string): ParsedModelLabel {
  let title = raw.trim();
  const badges: string[] = [];
  for (const token of BADGE_TOKENS) {
    const re = new RegExp(`\\b${token.replace(/\s+/g, '\\s+')}\\b`, 'i');
    if (re.test(title)) {
      badges.push(token);
      title = title.replace(re, '').replace(/\s+/g, ' ').trim();
    }
  }
  return { title: title || raw, badges };
}

export interface ModelOption {
  id: string;
  label: string;
  badges: string[];
}

export function resolveAgentModelId(
  agent: Agent | undefined,
  providers: ProviderConfig[],
  getLegacyProviderForAgent: (agentId: string) => ProviderConfig | undefined
): string | null {
  if (!agent) return null;
  if (agent.provider) {
    const provider = providers.find((p) => p.type === agent.provider && p.enabled);
    return agent.modelId || provider?.model || agent.resolvedModelId || null;
  }
  if (agent.providerId) {
    return (
      providers.find((p) => p.id === agent.providerId && p.enabled)?.model ||
      agent.modelId ||
      agent.resolvedModelId ||
      null
    );
  }
  return (
    agent.modelId ||
    getLegacyProviderForAgent(agent.id)?.model ||
    agent.resolvedModelId ||
    null
  );
}

export function modelsForAgent(
  agent: Agent,
  catalog: CatalogModel[],
  providerModels: Array<{ id: string; name: string }>
): ModelOption[] {
  const providerType = agent.provider ?? '';
  const fromCatalog = catalog
    .filter((m) => !providerType || m.provider === providerType)
    .map((m) => {
      const label = m.name ?? m.modelId;
      const parsed = parseModelLabel(label);
      return { id: m.modelId || m.canonicalId, label: parsed.title, badges: parsed.badges };
    });

  const fromProvider = providerModels.map((m) => {
    const parsed = parseModelLabel(m.name || m.id);
    return { id: m.id, label: parsed.title, badges: parsed.badges };
  });

  const merged = new Map<string, ModelOption>();
  for (const item of [...fromProvider, ...fromCatalog]) {
    if (item.id) merged.set(item.id, item);
  }

  const currentId = agent.modelId || agent.resolvedModelId;
  if (currentId && !merged.has(currentId)) {
    const label = modelDisplayName(catalog, currentId) ?? currentId;
    const parsed = parseModelLabel(label);
    merged.set(currentId, { id: currentId, label: parsed.title, badges: parsed.badges });
  }

  return Array.from(merged.values()).sort((a, b) => a.label.localeCompare(b.label));
}

/** Derive stub option toggles from a model id / label when backend has no explicit fields. */
export function modelOptionHints(modelId: string, label: string) {
  const hay = `${modelId} ${label}`.toLowerCase();
  return {
    thinking: hay.includes('thinking') || hay.includes('opus') || hay.includes('sonnet'),
    fast: hay.includes('fast'),
    effort: hay.includes('extra high')
      ? 'Extra High'
      : hay.includes('high')
        ? 'High'
        : hay.includes('medium')
          ? 'Medium'
          : hay.includes('low')
            ? 'Low'
            : hay.includes('max')
              ? 'Max'
              : null as string | null,
  };
}
