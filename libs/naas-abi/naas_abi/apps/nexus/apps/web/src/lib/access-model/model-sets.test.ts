import { describe, expect, it } from 'vitest';
import type { PolicyView } from '@/lib/iam-admin/types';
import { modelSets, modelsOf } from './model-sets';

const ACTIONS = ['model_registry:ListModels', 'model_registry:Resolve', 'model_registry:Chat', 'model_registry:ChatStream'];

function policy(name: string, resources: string[], over: Partial<PolicyView> = {}): PolicyView {
  return {
    id: `pol_${name}`,
    name,
    description: '',
    managed: false,
    revision: 1,
    owner_scope: 'abi:',
    document: { version: '2026-10-13', statements: [{ sid: 'ModelSet', effect: 'Allow', actions: ACTIONS, resources }] },
    created_at: null,
    updated_at: null,
    ...over,
  };
}

describe('model sets', () => {
  it('reads the models a set names, decoded', () => {
    const member = policy('Models · member', [
      'abi:model_registry:model/openai%2Fgpt-small',
      'abi:model_registry:model/mistral-small',
    ]);
    expect(modelsOf(member)).toEqual(['mistral-small', 'openai/gpt-small']);
    expect(modelsOf(policy('Models · all', ['abi:model_registry:model/*']))).toBe('all');
    const embeddings = policy('Models · embeddings', []);
    embeddings.document.statements = [
      { sid: 'Embed', effect: 'Allow', actions: ['model_registry:Embed'], resources: ['abi:model_registry:model/*'] },
      { sid: 'ResolveEmbeddingModels', effect: 'Allow', actions: ['model_registry:Resolve'], resources: ['abi:model_registry:model/embed-small'] },
    ];
    expect(modelsOf(embeddings)).toEqual(['embed-small']);
    // The empty set names a model no id can be.
    expect(modelsOf(policy('Models · member', ['abi:model_registry:model/%00']))).toEqual([]);
  });

  it('finds each set by its platform policy, the members’ default set first', () => {
    const sets = modelSets([
      policy('Models · all', ['abi:model_registry:model/*']),
      policy('Models · member', ['abi:model_registry:model/small']),
      // Someone's own policy of the same name in an organization is not the set.
      policy('Models · embeddings', ['abi:model_registry:model/embed'], { owner_scope: 'abi:nexus:organization/acme' }),
    ]);
    expect(sets.map((s) => [s.key, s.models, s.policy?.id ?? null])).toEqual([
      ['member', ['small'], 'pol_Models · member'],
      ['all', 'all', 'pol_Models · all'],
      ['embeddings', [], null],
    ]);
  });
});
