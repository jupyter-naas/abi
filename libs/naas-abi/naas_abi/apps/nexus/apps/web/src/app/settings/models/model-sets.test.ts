// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PolicyView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { fakeApi } from '@/components/access/access-fixtures';
import { ModelSets } from './model-sets';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const CHAT = ['model_registry:ListModels', 'model_registry:Resolve', 'model_registry:Chat', 'model_registry:ChatStream'];
const set = (name: string, resources: string[]): PolicyView => ({
  id: `pol_${name.split(' · ')[1]}`,
  name,
  description: '',
  managed: false,
  revision: 1,
  owner_scope: 'abi:',
  document: { version: '2026-10-13', statements: [{ effect: 'Allow', actions: CHAT, resources }] },
  created_at: null,
  updated_at: null,
});

const POLICIES = [
  set('Models · member', ['abi:model_registry:model/small', 'abi:model_registry:model/medium']),
  set('Models · all', ['abi:model_registry:model/*']),
];

const modelsAll = (over: Record<string, unknown> = {}) => ({
  capability: 'models_all' as const,
  name: 'Models · all',
  owner_scope: 'abi:',
  group_id: null,
  policy_id: null,
  can_create: true,
  ...over,
});

describe('Platform settings › Models › Sets', () => {
  it('shows the members’ default set and every model, read-only', async () => {
    const api = fakeApi({
      listPolicies: vi.fn().mockResolvedValue({ items: POLICIES, next_after: null }),
      capabilities: vi.fn().mockResolvedValue({ scope: 'abi:', capabilities: [modelsAll({ group_id: 'grp_all', can_create: false })] }),
    });
    mounted = await mount(ModelSets, { api });
    await mounted.flush();
    const member = document.querySelector('[data-model-set="member"]');
    expect([...member!.querySelectorAll('li')].map((li) => li.textContent)).toEqual(['medium', 'small']);
    expect(member?.textContent).toContain('nexus_config.models.member_set');
    expect(document.querySelector('[data-model-set="all"]')?.textContent).toContain('Every model');
    expect(document.querySelector('[data-model-set="all"] [data-capability] a')?.getAttribute('href')).toBe(
      '/settings/access/groups/grp_all',
    );
    expect(document.querySelector('[data-model-set="embeddings"]')?.textContent).toContain('not made yet');
    expect(document.querySelector('input, textarea, select')).toBeNull();
  });

  it('makes the group Models · all on demand', async () => {
    const ensureCapability = vi.fn().mockResolvedValue(modelsAll({ group_id: 'grp_all', can_create: false }));
    const api = fakeApi({
      listPolicies: vi.fn().mockResolvedValue({ items: POLICIES, next_after: null }),
      capabilities: vi.fn().mockResolvedValue({ scope: 'abi:', capabilities: [modelsAll()] }),
      ensureCapability,
    });
    mounted = await mount(ModelSets, { api });
    await mounted.flush();
    await mounted.click(document.querySelector('[data-action="create-capability"]'));
    await mounted.flush();
    expect(ensureCapability).toHaveBeenCalledWith('models_all', null);
    expect(document.querySelector('[data-model-set="all"] [data-capability] a')).not.toBeNull();
  });

  it('says the members’ set is empty when the configuration names none', async () => {
    const api = fakeApi({
      listPolicies: vi.fn().mockResolvedValue({ items: [set('Models · member', ['abi:model_registry:model/%00'])], next_after: null }),
      capabilities: vi.fn().mockRejectedValue(new Error('403')),
    });
    mounted = await mount(ModelSets, { api });
    await mounted.flush();
    expect(document.querySelector('[data-model-set="member"] [data-model-set-empty]')?.textContent).toContain(
      'Members chat with no model directly',
    );
  });
});
