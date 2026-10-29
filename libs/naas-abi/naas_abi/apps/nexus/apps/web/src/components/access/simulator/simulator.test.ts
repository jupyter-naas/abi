// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Simulation } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { ada, catalogsView, fakeApi } from '../access-fixtures';
import { headline, reasonText, statementFacts } from './simulator-model';
import { SimulatorView } from './simulator';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

const denied: Simulation = {
  allowed: false,
  reason: 'explicit_deny',
  action: 'triple_store:DropGraph',
  resource: 'abi:acme:ws-1:triple_store:graph/main',
  principal: ada,
  statement: {
    side: 'actor',
    principal_id: ada.id,
    effect: 'Deny',
    policy_id: 'pol_9',
    policy_name: 'No drops',
    statement_index: 1,
    sid: 'NoDrop',
    attachment_id: 'att_4',
    scope: 'abi:acme:ws-1',
    via_group: 'grp_ops',
    statement: { sid: 'NoDrop', effect: 'Deny', actions: ['triple_store:DropGraph'], resources: ['*'] },
  },
};

async function ask(result: Simulation | Error) {
  const simulate = vi.fn(() => (result instanceof Error ? Promise.reject(result) : Promise.resolve(result)));
  const api = fakeApi({
    simulate,
    listPrincipals: vi.fn().mockResolvedValue({ items: [ada], next_after: null }),
    catalogs: vi.fn().mockResolvedValue(catalogsView),
  });
  mounted = await mount(SimulatorView, { api, can: () => true });
  await mounted.flush();
  await mounted.type(field('Principal'), ada.id);
  await mounted.type(field('Action'), 'triple_store:DropGraph');
  await mounted.type(field('Resource'), 'abi:acme:ws-1:triple_store:graph/main');
  await mounted.click(button('Simulate') ?? null);
  await mounted.flush();
  return simulate;
}

describe('simulator wording', () => {
  it('says each reason in a sentence', () => {
    expect(reasonText('implicit_deny')).toContain('No statement allows it');
    expect(reasonText('explicit_deny')).toContain('explicit Deny always wins');
    expect(reasonText('sealed')).toContain('only its owner opens it');
    expect(headline({ allowed: true })).toBe('Allowed');
  });

  it('lists the facts of the deciding statement, leaving out what is missing', () => {
    expect(statementFacts({ ...denied.statement!, attachment_id: null, scope: null, via_group: null, sid: null })).toEqual([
      { label: 'Effect', value: 'Deny' },
      { label: 'Held by', value: 'the principal itself' },
      { label: 'Policy', value: 'No drops (pol_9)' },
      { label: 'Statement', value: '#2' },
    ]);
  });
});

describe('SimulatorView', () => {
  it('asks IAM and shows an explicit deny with the statement and its policy', async () => {
    const simulate = await ask(denied);
    expect(simulate).toHaveBeenCalledWith({
      principal_id: ada.id,
      action: 'triple_store:DropGraph',
      resource: 'abi:acme:ws-1:triple_store:graph/main',
    });

    const result = document.querySelector('[aria-label="Decision"]');
    expect(result?.textContent).toContain('Denied');
    expect(result?.textContent).toContain('explicit Deny always wins');
    const statement = document.querySelector('[aria-label="Deciding statement"]');
    expect(statement?.textContent).toContain('No drops (pol_9)');
    expect(statement?.textContent).toContain('#2 (NoDrop)');
    expect(statement?.textContent).toContain('Workspace ws-1 of acme');
    expect(statement?.textContent).toContain('grp_ops');
    expect(statement?.querySelector('pre')?.textContent).toContain('"effect": "Deny"');
  });

  it('says that nothing allowed an implicit deny', async () => {
    await ask({ ...denied, reason: 'implicit_deny', statement: null });
    const result = document.querySelector('[aria-label="Decision"]');
    expect(result?.textContent).toContain('Denied');
    expect(result?.textContent).toContain('No statement allows it');
    expect(result?.textContent).toContain('nothing names it');
    expect(document.querySelector('[aria-label="Deciding statement"]')).toBeNull();
  });

  it('shows an allow with the statement that grants it', async () => {
    await ask({
      ...denied,
      allowed: true,
      reason: 'allow',
      statement: { ...denied.statement!, effect: 'Allow', policy_name: 'Admin', policy_id: 'builtin.admin' },
    });
    const result = document.querySelector('[aria-label="Decision"]');
    expect(result?.textContent).toContain('Allowed');
    expect(result?.textContent).toContain('Admin (builtin.admin)');
  });

  it('suggests actions from the catalogs', async () => {
    mounted = await mount(SimulatorView, {
      api: fakeApi({
        listPrincipals: vi.fn().mockResolvedValue({ items: [], next_after: null }),
        catalogs: vi.fn().mockResolvedValue(catalogsView),
      }),
      can: () => true,
    });
    await mounted.flush();
    await mounted.type(field('Action'), 'triple_store:Dr');
    expect(document.querySelector('[role="option"]')?.textContent).toContain('triple_store:DropGraph');
  });

  it('shows IAM’s refusal, and does not run an incomplete question', async () => {
    await ask(new Error('You do not have permission to do this.'));
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('do not have permission');
    expect(document.querySelector('[aria-label="Decision"]')).toBeNull();

    await mounted!.type(field('Resource'), '');
    expect(button('Simulate')?.disabled).toBe(true);
  });
});
