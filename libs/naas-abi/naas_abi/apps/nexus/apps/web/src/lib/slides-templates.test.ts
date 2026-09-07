import { describe, expect, it } from 'vitest';

import {
  templateAssetLabel,
  templateNamespace,
  templateSlideLabel,
  templateNamespacesAreAmbiguous,
} from './slides-templates';

describe('templateSlideLabel', () => {
  it('joins eyebrow and title', () => {
    expect(templateSlideLabel({ eyebrow: 'Agenda', title: 'What we will cover' })).toBe(
      'Agenda: What we will cover',
    );
  });

  it('uses title when eyebrow matches', () => {
    expect(templateSlideLabel({ eyebrow: 'Context', title: 'Context' })).toBe('Context');
  });

  it('falls back to untitled', () => {
    expect(templateSlideLabel({ eyebrow: '', title: '' })).toBe('Untitled slide');
  });
});

describe('templateAssetLabel', () => {
  it('marks embedded assets', () => {
    expect(templateAssetLabel({ name: 'hero', kind: 'embedded' })).toBe('hero (embedded)');
  });
});

describe('templateNamespace', () => {
  it('prefers the source the API reported', () => {
    expect(templateNamespace({ id: 'abi/minimal-light-v1', source: 'acme' })).toBe('acme');
  });

  it('reads the prefix off the id when the API sent no source', () => {
    expect(templateNamespace({ id: 'acme/house-style-v1' })).toBe('acme');
  });

  it('leaves a bare id unnamespaced', () => {
    expect(templateNamespace({ id: 'minimal-light-v1' })).toBe('');
  });
});

describe('templateNamespacesAreAmbiguous', () => {
  it('is false when every template comes from one source', () => {
    expect(
      templateNamespacesAreAmbiguous([
        { id: 'abi/minimal-light-v1', source: 'abi' },
        { id: 'abi/pitch-dark-v1', source: 'abi' },
      ]),
    ).toBe(false);
  });

  it('is true once a second source contributes', () => {
    expect(
      templateNamespacesAreAmbiguous([
        { id: 'abi/minimal-light-v1', source: 'abi' },
        { id: 'acme/house-style-v1', source: 'acme' },
      ]),
    ).toBe(true);
  });

  it('is false for an empty catalog', () => {
    expect(templateNamespacesAreAmbiguous([])).toBe(false);
  });
});
