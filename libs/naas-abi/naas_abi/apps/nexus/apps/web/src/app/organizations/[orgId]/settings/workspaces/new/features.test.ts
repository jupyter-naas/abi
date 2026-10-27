import { describe, expect, it } from 'vitest';
import { featureChoices, featureOn, featuresPayload } from './features';

describe('the features of a new workspace', () => {
  it('offers the organization’s features, else the deployment’s', () => {
    expect(featureChoices({ catalog: ['chat', 'files', 'maps'], available: ['chat', 'files'] })).toEqual([
      'chat',
      'files',
    ]);
    expect(featureChoices({ catalog: ['chat', 'files'] })).toEqual(['chat', 'files']);
    expect(featureChoices(null)).toEqual([]);
  });

  it('sends null when every feature offered is on, else the checked ones in order', () => {
    const choices = ['chat', 'files', 'maps'];
    expect(featuresPayload(new Set(choices), choices)).toBeNull();
    expect(featuresPayload(new Set(['maps', 'chat']), choices)).toEqual(['chat', 'maps']);
    expect(featuresPayload(new Set(), choices)).toEqual([]);
  });

  it('counts every feature on until the catalog is known', () => {
    expect(featureOn('maps', null)).toBe(true);
    expect(featureOn('maps', new Set(['chat']))).toBe(false);
  });
});
