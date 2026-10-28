// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { formatPrice, formatTokens, modelRegistryView, perMillion } from './model-registry';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const render = async (node: ReactNode) => {
  mounted = await mount(() => createElement('div', null, node), {});
  return mounted.host;
};

const entry: ResourceEntry = {
  id: 'claude-opus-4',
  name: 'claude-opus-4',
  kind: 'item',
  actions: ['read', 'download'],
  size: null,
  modified: null,
  attributes: {
    kind: 'chat',
    providers: 'anthropic, openrouter',
    default: 'chat',
    display_name: 'Opus 4',
    context_window: '200000',
    max_output_tokens: '32000',
    input_price: '15',
    output_price: '75',
    summary: 'A coding model.',
  },
};

describe('model registry view', () => {
  it('formats tokens and prices', () => {
    expect(formatTokens(200000)).toBe('200K');
    expect(formatTokens(1_048_576)).toBe('1M');
    expect(formatTokens(2_000_000)).toBe('2M');
    expect(formatTokens(undefined)).toBe('—');
    expect(formatPrice('15')).toBe('$15');
    expect(formatPrice(0.075)).toBe('$0.075');
    expect(formatPrice(0)).toBe('free');
    expect(perMillion('0.000015')).toBeCloseTo(15);
  });

  it('shows catalog cards with kind, default and providers', async () => {
    const level = modelRegistryView.level!(0, '');
    const host = await render([modelRegistryView.badges!(entry), level.card!(entry), level.columns![1].render(entry), level.columns![0].render(entry)]);

    expect(level.layout).toBe('cards');
    expect(host.textContent).toContain('chat');
    expect(host.textContent).toContain('default chat');
    expect(host.textContent).toContain('Opus 4');
    expect(host.textContent).toContain('anthropic');
    expect(host.textContent).toContain('$15 / $75');
    expect(host.textContent).toContain('200K · 32K');
  });

  it('previews a model sheet with tiles and one row per provider', async () => {
    const detail: ResourceDetail = {
      entry,
      content: null,
      view: {
        type: 'json',
        value: {
          canonical_id: 'claude-opus-4',
          default_for: ['chat'],
          models: [
            {
              provider: 'openrouter',
              model_id: 'anthropic/claude-opus-4',
              kind: 'chat',
              description: 'Claude Opus 4 is the best coding model.',
              context_window: 200000,
              pricing: { prompt: '0.000015', completion: '0.000075' },
              architecture: { input_modalities: ['text', 'image'], output_modalities: ['text'] },
              supported_parameters: ['tools', 'temperature'],
            },
          ],
        },
      },
    };
    const host = await render(modelRegistryView.preview!(detail, {}));

    expect(host.querySelector('.data-models-sheet-title')?.textContent).toBe('Opus 4');
    expect(host.textContent).toContain('200K');
    expect(host.textContent).toContain('32K');
    expect(host.textContent).toContain('anthropic/claude-opus-4');
    expect(host.textContent).toContain('text, image');
    expect(host.textContent).toContain('temperature');
  });
});
