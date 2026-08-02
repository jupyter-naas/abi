import { describe, expect, it } from 'vitest';
import {
  availableModelOptions,
  formatAgentModelSubtitle,
  inferModelProviderLabel,
  modelOptionHints,
  normalizeAvailableProviders,
  parseModelLabel,
  shortenModelLabel,
} from './chat-agent-selector-utils';
import type { Agent } from '@/stores/agents';

const baseAgent = {
  id: 'zen',
  name: 'Zen',
  description: '',
  icon: 'sparkles' as const,
  systemPrompt: '',
  providerId: null,
  provider: 'abi',
  modelId: null,
  resolvedModelId: 'qwen-2.5-3b',
  logoUrl: null,
  enabled: true,
  tools: [],
  capabilities: { memory: false, reasoning: false, vision: false },
  intentMappings: [],
  isDefault: true,
  createdAt: new Date(),
  updatedAt: new Date(),
} satisfies Agent;

describe('parseModelLabel', () => {
  it('splits title and badges from model names', () => {
    expect(parseModelLabel('Opus 5 High Fast')).toEqual({
      title: 'Opus 5',
      badges: ['High Fast'],
    });
  });

  it('handles names without badges', () => {
    expect(parseModelLabel('Composer 2.5')).toEqual({
      title: 'Composer 2.5',
      badges: [],
    });
  });
});

describe('modelOptionHints', () => {
  it('infers thinking and effort from model metadata', () => {
    const hints = modelOptionHints('claude-opus-5-high', 'Opus 5 High');
    expect(hints.thinking).toBe(true);
    expect(hints.effort).toBe('High');
  });
});

describe('shortenModelLabel', () => {
  it('strips provider prefixes and path segments', () => {
    expect(shortenModelLabel('openrouter/anthropic/claude-sonnet-5')).toBe('claude-sonnet-5');
    expect(shortenModelLabel('ollama/qwen-2.5-3b')).toBe('qwen-2.5-3b');
  });
});

describe('formatAgentModelSubtitle', () => {
  it('formats local-first ABI resolved model as ollama meta', () => {
    expect(formatAgentModelSubtitle(baseAgent, 'qwen-2.5-3b', [])).toBe(
      'ollama · qwen-2.5-3b'
    );
  });

  it('uses catalog provider when present', () => {
    expect(
      formatAgentModelSubtitle(baseAgent, 'claude-sonnet-5', [
        {
          canonicalId: 'claude-sonnet-5',
          modelId: 'claude-sonnet-5',
          provider: 'openrouter',
          name: 'Claude Sonnet 5',
        },
      ])
    ).toBe('openrouter · claude-sonnet-5');
  });

  it('returns null when model is missing', () => {
    expect(formatAgentModelSubtitle(baseAgent, null, [])).toBeNull();
  });
});

describe('inferModelProviderLabel', () => {
  it('keeps non-abi agent provider', () => {
    expect(
      inferModelProviderLabel(
        { ...baseAgent, provider: 'openrouter', modelId: 'claude-sonnet-5' },
        'claude-sonnet-5',
        []
      )
    ).toBe('openrouter');
  });
});

describe('normalizeAvailableProviders', () => {
  it('maps catalog shape (configured/model_id) to picker shape', () => {
    const normalized = normalizeAvailableProviders([
      {
        id: 'openrouter',
        name: 'OpenRouter',
        configured: false,
        has_api_key: true,
        models: [
          {
            canonical_id: 'claude-sonnet-5',
            model_id: 'anthropic/claude-sonnet-5',
            name: 'Claude Sonnet 5',
          },
        ],
      },
    ]);
    expect(normalized[0]).toMatchObject({
      id: 'openrouter',
      type: 'openrouter',
      has_api_key: true,
      models: [{ id: 'anthropic/claude-sonnet-5', name: 'Claude Sonnet 5' }],
    });
  });
});

describe('availableModelOptions', () => {
  it('includes ollama always and cloud only when keyed', () => {
    const options = availableModelOptions(
      [
        {
          id: 'ollama',
          type: 'ollama',
          name: 'Ollama',
          has_api_key: false,
          models: [{ id: 'qwen-2.5-3b', name: 'Qwen 2.5 3B' }],
        },
        {
          id: 'openrouter',
          type: 'openrouter',
          name: 'OpenRouter',
          has_api_key: true,
          models: [{ id: 'claude-sonnet-5', name: 'Claude Sonnet 5' }],
        },
        {
          id: 'anthropic',
          type: 'anthropic',
          name: 'Anthropic',
          has_api_key: false,
          models: [{ id: 'claude-opus-5', name: 'Claude Opus 5' }],
        },
      ],
      [],
      'qwen-2.5-3b'
    );
    const labels = options.map((o) => o.label);
    expect(labels).toContain('ollama · qwen-2.5-3b');
    expect(labels).toContain('openrouter · claude-sonnet-5');
    expect(labels.some((l) => l.includes('claude-opus-5'))).toBe(false);
  });
});
