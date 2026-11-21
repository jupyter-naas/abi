import { describe, expect, it } from 'vitest';
import type { OfferState } from '@/lib/access-model/workspace-offer';
import type { PublishersView } from '@/lib/iam-admin/types';
import {
  draftKey,
  featureChanges,
  isOffered,
  itemName,
  modulesOf,
  offerChanges,
  unsavedCount,
  wholeModule,
} from './offer-model';

const offered = (over: Partial<OfferState['offered']> = {}): OfferState['offered'] => ({
  agents: [],
  apps: [],
  workflows: [],
  pipelines: [],
  ...over,
});

describe('what a workspace offers', () => {
  it('offers an item by name or with its whole module', () => {
    const now = offered({ agents: [{ module: 'acme.people', name: 'Coach' }, { module: 'acme.market', name: '*' }] });
    expect(isOffered(now, 'agents', 'acme.people', 'Coach')).toBe(true);
    expect(isOffered(now, 'agents', 'acme.people', 'Recruiter')).toBe(false);
    expect(isOffered(now, 'agents', 'acme.market', 'Analyst')).toBe(true);
    expect(wholeModule(now, 'agents', 'acme.market')).toBe(true);
    expect(wholeModule(now, 'apps', 'acme.market')).toBe(false);
  });

  it('reads a draft over what is offered', () => {
    const now = offered({ agents: [{ module: 'acme.people', name: 'Coach' }] });
    const drafts = { [draftKey('agents', 'acme.people', 'Coach')]: false, [draftKey('apps', 'acme.people', '*')]: true };
    expect(isOffered(now, 'agents', 'acme.people', 'Coach', drafts)).toBe(false);
    expect(isOffered(now, 'apps', 'acme.people', 'Board', drafts)).toBe(true);
  });

  it('sends only the toggles that change what is offered', () => {
    const now = offered({ agents: [{ module: 'acme.people', name: 'Coach' }] });
    const drafts = {
      [draftKey('agents', 'acme.people', 'Coach')]: true, // unchanged
      [draftKey('agents', 'acme.people', 'Recruiter')]: true,
      [draftKey('workflows', 'acme.sales', '*')]: true,
      [draftKey('agents', 'acme.people', 'Ghost')]: false, // never offered
    };
    expect(offerChanges(now, drafts)).toEqual([
      { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
      { kind: 'workflows', module: 'acme.sales', name: '*', offered: true },
    ]);
    expect(unsavedCount(now, drafts, [], {})).toBe(2);
  });

  it('names an item by its listed id', () => {
    expect(itemName('acme.people', 'acme.people/Coach')).toBe('Coach');
    expect(itemName('acme.people', 'Coach')).toBe('Coach');
  });

  it('lists the modules IAM lets the caller offer, and those already offered, by name', () => {
    const publishers: PublishersView = {
      scope: 'abi:x',
      publishers: [
        { id: 'naas_abi', kind: 'naas_abi', types: [] },
        {
          id: 'acme.people',
          kind: 'module',
          types: [
            { service: 'module', type: 'agent', description: '', id: 'path', placement: 'placed', container: false, listed: true, module: 'acme.people', actions: [] },
            { service: 'module', type: 'workflow', description: '', id: 'path', placement: 'placed', container: false, listed: true, module: 'acme.people', actions: [] },
          ],
        },
      ],
    };
    const now = offered({ apps: [{ module: 'zeta.old', name: '*' }] });
    expect(modulesOf(publishers, now)).toEqual([
      { module: 'acme.people', kinds: ['agents', 'workflows'], grantable: true },
      { module: 'zeta.old', kinds: ['apps'], grantable: false },
    ]);
  });

  it('turns feature toggles into Everyone or Nobody', () => {
    const rows = [
      { key: 'chat', choice: 'everyone' as const },
      { key: 'maps', choice: 'nobody' as const },
    ];
    expect(featureChanges(rows, { chat: false, maps: false })).toEqual([{ feature: 'chat', choice: 'nobody' }]);
    expect(featureChanges(rows, { maps: true })).toEqual([{ feature: 'maps', choice: 'everyone' }]);
  });
});
