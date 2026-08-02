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
  provider?: string;
}

/** Compact model id for muted meta (Cursor-style secondary text). */
export function shortenModelLabel(modelId: string): string {
  let s = modelId.trim();
  if (!s) return s;
  s = s.replace(/^(ollama|openrouter|openai|anthropic|google|xai|mistral)\//i, '');
  if (s.includes('/')) {
    s = s.split('/').filter(Boolean).pop() || s;
  }
  return s;
}

/**
 * Resolve which LLM id an agent row should advertise.
 * Prefer explicit modelId, then backend resolved_model_id, then provider default.
 */
export function resolveAgentModelId(
  agent: Agent | undefined,
  providers: ProviderConfig[],
  getLegacyProviderForAgent: (agentId: string) => ProviderConfig | undefined
): string | null {
  if (!agent) return null;
  if (agent.provider) {
    const provider = providers.find((p) => p.type === agent.provider && p.enabled);
    // ABI agents: model on the provider config is agent identity, not the LLM.
    if (agent.provider === 'abi') {
      return agent.modelId || agent.resolvedModelId || null;
    }
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

/** Infer a short provider label for muted subtitle text. */
export function inferModelProviderLabel(
  agent: Agent,
  modelId: string,
  catalog: CatalogModel[]
): string {
  if (agent.provider && agent.provider !== 'abi') {
    return agent.provider.toLowerCase();
  }
  const entry = catalog.find((m) => m.modelId === modelId || m.canonicalId === modelId);
  if (entry?.provider) return entry.provider.toLowerCase();

  const hay = modelId.toLowerCase();
  if (hay.includes('claude') || hay.includes('anthropic')) return 'anthropic';
  if (hay.includes('gpt') || hay.includes('o1') || hay.includes('o3')) return 'openai';
  if (hay.includes('gemini')) return 'google';
  if (hay.includes('grok')) return 'xai';
  // Local-first default for ABI / unresolved ids (qwen, llama, etc.).
  return 'ollama';
}

/**
 * Cursor-style muted meta next to an agent name, e.g. `ollama · qwen-2.5-3b`.
 * Returns null when no model can be resolved.
 */
export function formatAgentModelSubtitle(
  agent: Agent,
  modelId: string | null | undefined,
  catalog: CatalogModel[]
): string | null {
  if (!modelId) return null;
  const provider = inferModelProviderLabel(agent, modelId, catalog);
  return `${provider} · ${shortenModelLabel(modelId)}`;
}

export interface AvailableProviderModels {
  id: string;
  type: string;
  name: string;
  has_api_key: boolean;
  models: Array<{ id: string; name: string }>;
}

/** Normalize catalog `/api/providers/available` into the picker shape. */
export function normalizeAvailableProviders(raw: unknown): AvailableProviderModels[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) => {
    const p = entry as Record<string, unknown>;
    const id = String(p.id || '');
    const configured = Boolean(p.configured);
    const hasKey = Boolean(p.has_api_key ?? configured);
    const modelsRaw = Array.isArray(p.models) ? p.models : [];
    return {
      id,
      type: String(p.type || id),
      name: String(p.name || id),
      has_api_key: hasKey,
      models: modelsRaw
        .map((m) => {
          const row = m as Record<string, unknown>;
          const modelId = String(row.id || row.model_id || row.canonical_id || '');
          if (!modelId) return null;
          return {
            id: modelId,
            name: String(row.name || modelId),
          };
        })
        .filter((m): m is { id: string; name: string } => m != null),
    };
  });
}

/**
 * Build switcher options from `/api/providers/available`.
 * Ollama is always included; cloud providers only when a key is present.
 */
export function availableModelOptions(
  available: AvailableProviderModels[],
  catalog: CatalogModel[],
  currentModelId?: string | null
): ModelOption[] {
  const merged = new Map<string, ModelOption>();
  const providers = normalizeAvailableProviders(available);

  for (const p of providers) {
    const usable = p.type === 'ollama' || p.has_api_key;
    if (!usable) continue;
    for (const m of p.models || []) {
      if (!m?.id) continue;
      const parsed = parseModelLabel(m.name || m.id);
      const key = `${p.type}:${m.id}`;
      merged.set(key, {
        id: m.id,
        provider: p.type,
        label: `${p.type} · ${shortenModelLabel(m.id)}`,
        badges: parsed.badges,
      });
    }
  }

  // Catalog fills gaps for providers already represented above.
  const enabledTypes = new Set(
    providers
      .filter((p) => p.type === 'ollama' || p.has_api_key)
      .map((p) => p.type.toLowerCase())
  );
  for (const m of catalog) {
    if (!m.modelId || !enabledTypes.has((m.provider || '').toLowerCase())) continue;
    const key = `${m.provider}:${m.modelId}`;
    if (merged.has(key)) continue;
    const parsed = parseModelLabel(m.name ?? m.modelId);
    merged.set(key, {
      id: m.modelId,
      provider: m.provider,
      label: `${m.provider} · ${shortenModelLabel(m.modelId)}`,
      badges: parsed.badges,
    });
  }

  if (currentModelId && ![...merged.values()].some((o) => o.id === currentModelId)) {
    const label = modelDisplayName(catalog, currentModelId) ?? currentModelId;
    const parsed = parseModelLabel(label);
    merged.set(`current:${currentModelId}`, {
      id: currentModelId,
      label: shortenModelLabel(currentModelId),
      badges: parsed.badges,
    });
  }

  return Array.from(merged.values()).sort((a, b) => a.label.localeCompare(b.label));
}

export function modelsForAgent(
  agent: Agent,
  catalog: CatalogModel[],
  providerModels: Array<{ id: string; name: string }>
): ModelOption[] {
  const providerType = agent.provider && agent.provider !== 'abi' ? agent.provider : '';
  const fromCatalog = catalog
    .filter((m) => !providerType || m.provider === providerType)
    .map((m) => {
      const label = m.name ?? m.modelId;
      const parsed = parseModelLabel(label);
      return {
        id: m.modelId || m.canonicalId,
        provider: m.provider,
        label: parsed.title,
        badges: parsed.badges,
      };
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
