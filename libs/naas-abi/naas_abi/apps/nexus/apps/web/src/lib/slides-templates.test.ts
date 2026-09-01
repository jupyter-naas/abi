import { describe, expect, it } from 'vitest';

import { templateAssetLabel, templateSlideLabel } from './slides-templates';

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
