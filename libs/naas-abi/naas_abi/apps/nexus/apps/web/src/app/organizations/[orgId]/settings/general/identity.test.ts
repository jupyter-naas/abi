import { describe, expect, it } from 'vitest';

import {
  identityChanges,
  identityFrom,
  identitySaveError,
  normalizeWebsite,
} from './identity';

describe('identityFrom', () => {
  it('reads every field, blank when missing or not text', () => {
    const identity = identityFrom({ name: 'Acme', city: 'Paris', website: null });
    expect(identity.name).toBe('Acme');
    expect(identity.city).toBe('Paris');
    expect(identity.website).toBe('');
    expect(identity.legal_name).toBe('');
  });
});

describe('identityChanges', () => {
  const initial = identityFrom({ name: 'Acme', city: 'Paris', country: 'France' });

  it('sends only what changed, trimmed', () => {
    expect(identityChanges(initial, { ...initial, city: ' Lyon ', legal_name: 'Acme SAS' })).toEqual({
      city: 'Lyon',
      legal_name: 'Acme SAS',
    });
  });

  it('sends a cleared field as null', () => {
    expect(identityChanges(initial, { ...initial, country: '  ' })).toEqual({ country: null });
  });

  it('never clears the name', () => {
    expect(identityChanges(initial, { ...initial, name: '' })).toEqual({});
  });

  it('is empty when nothing changed but spaces', () => {
    expect(identityChanges(initial, { ...initial, city: 'Paris ' })).toEqual({});
  });
});

describe('normalizeWebsite', () => {
  it('adds https to a bare host and keeps a full URL', () => {
    expect(normalizeWebsite('acme.com')).toBe('https://acme.com');
    expect(normalizeWebsite('http://localhost:3000')).toBe('http://localhost:3000');
    expect(normalizeWebsite('  ')).toBe('');
  });
});

describe('identitySaveError', () => {
  it('names the refusal', () => {
    expect(identitySaveError(403, 'Only admins can update organization branding')).toMatch(/administrators/);
    expect(identitySaveError(422, [{ loc: ['body', 'website'] }])).toMatch(/website/);
    expect(identitySaveError(422, [{ loc: ['body', 'contact_email'] }])).toMatch(/contact email/);
    expect(identitySaveError(422, [{ loc: ['body', 'postal_code'] }])).toBe('Check postal code.');
    expect(identitySaveError(500, null)).toBe('The changes could not be saved.');
  });
});

describe('identityCreateFields', () => {
  it('sends what is filled in, trimmed, the website made a URL, never the name', async () => {
    const { identityCreateFields } = await import('./identity');
    const values = identityFrom({ name: 'Acme', legal_name: ' Acme SAS ', website: 'acme.com', city: '  ' });
    expect(identityCreateFields(values)).toEqual({ legal_name: 'Acme SAS', website: 'https://acme.com' });
  });
});
