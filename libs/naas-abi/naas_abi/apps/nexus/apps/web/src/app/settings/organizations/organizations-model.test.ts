import { describe, expect, it } from 'vitest';
import { deleteConfirmed, errorText, slugFromName, sortOrganizations } from './organizations-model';

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
