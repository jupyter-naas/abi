import { describe, expect, it } from 'vitest';
import type { OfferState } from '@/lib/access-model/workspace-offer';
import type { PublishersView } from '@/lib/iam-admin/types';
import {
  catalogItems,
  catalogModules,
  enabledChanges,
  enabledLabel,
  moduleItemKey,
  type ModuleItem,
} from './module-items-model';

const offered = (over: Partial<OfferState['offered']> = {}): OfferState['offered'] => ({
  agents: [],
  apps: [],
  workflows: [],
  pipelines: [],
  ...over,
});

const PUBLISHERS: PublishersView = {
  scope: 'abi:nexus:workspace/ws-1',
  publishers: [
    {
      id: 'acme.people',
      kind: 'module',
      types: [
        { service: 'module', type: 'agent', module: 'acme.people' },
        { service: 'module', type: 'workflow', module: 'acme.people' },
      ],
    },
    { id: 'nexus', kind: 'service', types: [{ service: 'nexus', type: 'workspace', module: null }] },
  ],
} as unknown as PublishersView;

describe('the modules a page lists the items of', () => {
  it('takes the kinds asked of the modules IAM lets the caller give, and of those offered', () => {
    const modules = catalogModules(
      PUBLISHERS,
      offered({ agents: [{ module: 'acme.market', name: 'Trader' }] }),
      ['agents'],
    );
    expect(modules).toEqual([
      { kind: 'agents', module: 'acme.market', grantable: false },
      { kind: 'agents', module: 'acme.people', grantable: true },
    ]);
    expect(catalogModules(PUBLISHERS, offered(), ['workflows', 'pipelines'])).toEqual([
      { kind: 'workflows', module: 'acme.people', grantable: true },
    ]);
  });
});

describe('every item of a module, offered or not', () => {
  it('lists the items listed, those offered by name the listing missed, each enabled or not', () => {
    const items = catalogItems(
      [
        {
          kind: 'agents',
          module: 'acme.people',
          grantable: true,
          items: [
            { name: 'Coach', label: 'Coach' },
            { name: 'Recruiter', label: 'Recruiter' },
          ],
        },
      ],
      offered({ agents: [{ module: 'acme.people', name: 'Coach' }, { module: 'acme.people', name: 'Gone' }] }),
    );
    expect(items.map((item) => [item.name, item.offered])).toEqual([
      ['Coach', true],
      ['Gone', true],
      ['Recruiter', false],
    ]);
    expect(moduleItemKey(items[0])).toBe('agents|acme.people|Coach');
    expect(enabledLabel(items[0])).toBe('Enabled');
    expect(enabledLabel(items[2])).toBe('Disabled');
  });

  it('enables every item of a module offered whole', () => {
    const items = catalogItems(
      [{ kind: 'apps', module: 'acme.apps', grantable: true, items: [{ name: 'crm', label: 'CRM' }] }],
      offered({ apps: [{ module: 'acme.apps', name: '*' }] }),
    );
    expect(items).toEqual([{ kind: 'apps', module: 'acme.apps', name: 'crm', label: 'CRM', offered: true, grantable: true }]);
  });
});

describe('what enabling or disabling items sends', () => {
  const item = (name: string, on: boolean, over: Partial<ModuleItem> = {}): ModuleItem => ({
    kind: 'agents',
    module: 'acme.people',
    name,
    label: name,
    offered: on,
    grantable: true,
    ...over,
  });

  it('enables one item by its name', () => {
    const state = offered();
    expect(enabledChanges(state, [item('Coach', false)], [item('Coach', false)], true)).toEqual([
      { kind: 'agents', module: 'acme.people', name: 'Coach', offered: true },
    ]);
  });

  it('disables one item offered by its name', () => {
    const state = offered({ agents: [{ module: 'acme.people', name: 'Coach' }] });
    expect(enabledChanges(state, [item('Coach', true)], [item('Coach', true)], false)).toEqual([
      { kind: 'agents', module: 'acme.people', name: 'Coach', offered: false },
    ]);
  });

  it('sends nothing for an item already as asked', () => {
    const state = offered({ agents: [{ module: 'acme.people', name: 'Coach' }] });
    expect(enabledChanges(state, [item('Coach', true)], [item('Coach', true)], true)).toEqual([]);
    expect(enabledChanges(state, [item('Recruiter', false)], [item('Recruiter', false)], false)).toEqual([]);
  });

  it('turns a module offered whole into item by item when one of its items is disabled', () => {
    const state = offered({
      agents: [{ module: 'acme.people', name: '*' }],
      workflows: [{ module: 'acme.people', name: '*' }],
    });
    const catalog = [
      item('Coach', true),
      item('Recruiter', true),
      item('Scout', true),
      item('Other', true, { module: 'acme.market' }),
      item('sync', true, { kind: 'workflows' }),
    ];
    expect(enabledChanges(state, catalog, [catalog[0]], false)).toEqual([
      { kind: 'agents', module: 'acme.people', name: '*', offered: false },
      { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
      { kind: 'agents', module: 'acme.people', name: 'Scout', offered: true },
    ]);
  });

  it('disables several items of a module offered whole in one change, the others kept', () => {
    const state = offered({ agents: [{ module: 'acme.people', name: '*' }, { module: 'acme.people', name: 'Scout' }] });
    const catalog = [item('Coach', true), item('Recruiter', true), item('Scout', true)];
    expect(enabledChanges(state, catalog, [catalog[0], catalog[1]], false)).toEqual([
      { kind: 'agents', module: 'acme.people', name: '*', offered: false },
    ]);
    expect(enabledChanges(state, catalog, catalog, false)).toEqual([
      { kind: 'agents', module: 'acme.people', name: '*', offered: false },
      { kind: 'agents', module: 'acme.people', name: 'Scout', offered: false },
    ]);
  });

  it('enables a batch item by item, those already enabled left out', () => {
    const state = offered({ agents: [{ module: 'acme.people', name: 'Coach' }] });
    const catalog = [item('Coach', true), item('Recruiter', false), item('Trader', false, { module: 'acme.market' })];
    expect(enabledChanges(state, catalog, catalog, true)).toEqual([
      { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
      { kind: 'agents', module: 'acme.market', name: 'Trader', offered: true },
    ]);
  });
});
