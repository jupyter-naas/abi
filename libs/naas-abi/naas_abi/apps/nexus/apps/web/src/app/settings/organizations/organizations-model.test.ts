import { describe, expect, it } from 'vitest';
import {
  deleteConfirmed,
  errorText,
  matchesOrganization,
  organizationCount,
  organizationLocation,
  slugFromName,
  sortOrganizations,
  sortOrganizationsBy,
  websiteLabel,
} from './organizations-model';

describe('slugFromName', () => {
  it('suggests lowercase words joined by dashes', () => {
    expect(slugFromName('Beta Corp')).toBe('beta-corp');
    expect(slugFromName('  Acmé & Sons!  ')).toBe('acme-sons');
    expect(slugFromName('')).toBe('');
  });
});

describe('deleteConfirmed', () => {
  const beta = { id: 'org-b', name: 'Beta Corporation', slug: 'beta' };
  it('needs the name typed back exactly', () => {
    expect(deleteConfirmed(beta, 'Beta Corporation')).toBe(true);
    expect(deleteConfirmed(beta, ' Beta Corporation ')).toBe(true);
    expect(deleteConfirmed(beta, 'beta corporation')).toBe(false);
    expect(deleteConfirmed(beta, 'beta')).toBe(false);
    expect(deleteConfirmed(beta, '')).toBe(false);
  });
});

describe('errorText', () => {
  it('is the API detail when it is text', () => {
    expect(errorText(409, { detail: 'Organization org-a still has workspaces: Alpha (ws-1). Delete them first' })).toContain(
      'Alpha (ws-1)'
    );
    expect(errorText(400, { detail: 'Slug already exists' })).toBe('Slug already exists');
  });
  it('reads a validation error, else names the status', () => {
    expect(errorText(422, { detail: [{ msg: 'field required' }] })).toBe('field required');
    expect(errorText(403, null)).toBe('You may not do this.');
    expect(errorText(404, {})).toBe('Organization not found.');
    expect(errorText(500, {})).toBe('The API answered 500.');
  });
});

describe('sortOrganizations', () => {
  it('sorts by name, then id', () => {
    const sorted = sortOrganizations([
      { id: 'b', name: 'Beta', slug: 'b' },
      { id: 'a2', name: 'Acme', slug: 'a2' },
      { id: 'a1', name: 'Acme', slug: 'a1' },
    ]);
    expect(sorted.map((o) => o.id)).toEqual(['a1', 'a2', 'b']);
  });
});

describe('the organizations table', () => {
  const acme = { id: 'org-a', name: 'Acme', slug: 'acme', city: 'Paris', country: 'France', website: 'https://acme.example/' };
  const beta = { id: 'org-b', name: 'Beta', slug: 'beta', legal_name: 'Beta SA', city: null, country: 'Belgium' };
  const gamma = { id: 'org-c', name: 'Gamma', slug: 'gamma' };

  it('reads the location and the website as people say them', () => {
    expect(organizationLocation(acme)).toBe('Paris, France');
    expect(organizationLocation(beta)).toBe('Belgium');
    expect(organizationLocation(gamma)).toBe('');
    expect(websiteLabel('https://acme.example/')).toBe('acme.example');
    expect(websiteLabel(null)).toBe('');
  });

  it('searches every word across name, slug, id, legal name, location and website', () => {
    expect(matchesOrganization(acme, 'paris acme')).toBe(true);
    expect(matchesOrganization(beta, 'beta sa')).toBe(true);
    expect(matchesOrganization(acme, 'acme.example')).toBe(true);
    expect(matchesOrganization(gamma, 'paris')).toBe(false);
    expect(matchesOrganization(gamma, '  ')).toBe(true);
  });

  it('sorts by a column, blanks last both ways', () => {
    const ids = (dir: 'asc' | 'desc') => sortOrganizationsBy([gamma, beta, acme], 'location', dir).map((o) => o.id);
    expect(ids('asc')).toEqual(['org-b', 'org-a', 'org-c']);
    expect(ids('desc')).toEqual(['org-a', 'org-b', 'org-c']);
  });

  it('counts organizations', () => {
    expect(organizationCount(1)).toBe('1 organization');
    expect(organizationCount(3)).toBe('3 organizations');
  });
});
