import { describe, expect, it } from 'vitest';
import { grantedLinks, policyDriven, policyOfSearch, withPolicy } from './settings-policy';

const link = (page: string) => ({ href: `/workspace/ws-1/settings/${page}`, label: page });

describe('the policy the Features and Access pages set (`?policy=`)', () => {
  it('drives Access › Features, Core Services, Modules and every page under Features, nothing else', () => {
    for (const page of ['features', 'core-services', 'modules', 'agents', 'datasets', 'files', 'workflows'])
      expect(policyDriven(link(page).href)).toBe(true);
    for (const page of ['general', 'users', 'policies', 'groups'])
      expect(policyDriven(link(page).href)).toBe(false);
    // A page under one of them too (an agent's page).
    expect(policyDriven('/workspace/ws-1/settings/agents/a-1')).toBe(true);
  });

  it('is carried by a link, and left out for "<W> access"', () => {
    expect(withPolicy('/workspace/ws-1/settings/datasets', 'pol 2')).toBe('/workspace/ws-1/settings/datasets?policy=pol%202');
    expect(withPolicy('/workspace/ws-1/settings/datasets', null)).toBe('/workspace/ws-1/settings/datasets');
    expect(withPolicy('/workspace/ws-1/settings/modules?module=acme', 'p')).toBe('/workspace/ws-1/settings/modules?module=acme&policy=p');
    expect(policyOfSearch(new URLSearchParams('policy=p&x=1'))).toBe('p');
    expect(policyOfSearch(new URLSearchParams(''))).toBeNull();
  });

  it('with another policy picked, keeps the pages of the features it grants (Files by its feature)', () => {
    const links = ['agents', 'datasets', 'files', 'graphs', 'workflows'].map(link);
    expect(grantedLinks(links, new Set(['agents', 'files'])).map((l) => l.label)).toEqual(['agents', 'files', 'workflows']);
    // "<W> access": what the workspace offers, as the nav already shows it.
    expect(grantedLinks(links, null)).toEqual(links);
  });
});
