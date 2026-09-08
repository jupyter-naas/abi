import { describe, expect, it } from 'vitest';

import { DEFAULT_SLIDES_TEMPLATE_ID } from './create-slides-project';
import {
  DEFAULT_TEMPLATE_PREVIEW,
  SLIDES_HOME_BLANK_TEMPLATE_ID,
  slidesHomeTemplateCards,
  slidesTemplateMenuRows,
  templateAssetLabel,
  templateDisplayName,
  templateNamespace,
  templateNamespaceLabel,
  templatePreviewColors,
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

describe('templateNamespaceLabel', () => {
  it('uses the known source names', () => {
    expect(templateNamespaceLabel('abi')).toBe('ABI');
    expect(templateNamespaceLabel('forvis-mazars')).toBe('Forvis Mazars');
  });

  it('title-cases an unknown slug', () => {
    expect(templateNamespaceLabel('acme-house')).toBe('Acme House');
  });
});

describe('slidesHomeTemplateCards', () => {
  it('pins Blank to the default seed even when the catalog is empty', () => {
    expect(slidesHomeTemplateCards([])).toEqual([
      { id: DEFAULT_SLIDES_TEMPLATE_ID, label: 'Blank', blank: true },
    ]);
    expect(SLIDES_HOME_BLANK_TEMPLATE_ID).toBe(DEFAULT_SLIDES_TEMPLATE_ID);
  });

  it('puts Forvis Mazars AI second, then the remaining human names', () => {
    const cards = slidesHomeTemplateCards([
      { id: 'forvis-mazars/financial-services-v2', name: 'Financial services' },
      { id: 'forvis-mazars/fm-slides-v1', name: 'Forvis Mazars AI' },
      { id: 'abi/minimal-light-v1', name: 'Minimal Light' },
      { id: 'abi/pitch-dark-v1', name: 'Pitch Dark' },
    ]);
    expect(cards.map((card) => card.label)).toEqual([
      'Blank',
      'Forvis Mazars AI',
      'Financial services',
      'Pitch Dark',
    ]);
    expect(cards[0]?.id).toBe('abi/minimal-light-v1');
    expect(cards[1]?.id).toBe('forvis-mazars/fm-slides-v1');
    expect(cards.every((card) => !card.label.includes('/'))).toBe(true);
  });
});

describe('slidesTemplateMenuRows', () => {
  it('lists names only when every seed is from one source', () => {
    const rows = slidesTemplateMenuRows([
      { id: 'abi/minimal-light-v1', source: 'abi', name: 'Minimal Light', preview_accent: '#111' },
      { id: 'abi/pitch-dark-v1', source: 'abi', name: 'Pitch Dark', preview_accent: '#222' },
    ]);
    expect(rows).toEqual([
      { kind: 'template', id: 'abi/minimal-light-v1', label: 'Minimal Light', swatch: '#111' },
      { kind: 'template', id: 'abi/pitch-dark-v1', label: 'Pitch Dark', swatch: '#222' },
    ]);
  });

  it('inserts source headings instead of prefixing each row', () => {
    const rows = slidesTemplateMenuRows([
      { id: 'abi/minimal-light-v1', source: 'abi', name: 'Minimal Light' },
      {
        id: 'forvis-mazars/financial-services-v2',
        source: 'forvis-mazars',
        name: 'Financial services',
      },
    ]);
    expect(rows.map((row) => row.label)).toEqual([
      'ABI',
      'Minimal Light',
      'Forvis Mazars',
      'Financial services',
    ]);
    expect(rows.every((row) => !row.label.includes('/'))).toBe(true);
    expect(rows.find((row) => row.kind === 'template' && row.label === 'Financial services')?.id).toBe(
      'forvis-mazars/financial-services-v2',
    );
  });
});

describe('templatePreviewColors', () => {
  const catalog = [
    {
      id: 'abi/minimal-light-v1',
      preview_bg: '#f7f6f3',
      preview_panel: '#ffffff',
      preview_accent: '#1a1a1a',
      preview_ink: '#1a1a1a',
    },
  ];

  it('matches a namespaced id or a bare stem', () => {
    expect(templatePreviewColors('abi/minimal-light-v1', catalog).preview_bg).toBe('#f7f6f3');
    expect(templatePreviewColors('minimal-light-v1', catalog).preview_accent).toBe('#1a1a1a');
  });

  it('falls back to seed defaults', () => {
    expect(templatePreviewColors('missing', catalog)).toEqual(DEFAULT_TEMPLATE_PREVIEW);
    expect(templatePreviewColors('', [])).toEqual(DEFAULT_TEMPLATE_PREVIEW);
  });
});

describe('templateDisplayName', () => {
  const catalog = [
    { id: 'abi/minimal-light-v1', name: 'Minimal Light' },
    { id: 'forvis-mazars/fm-slides-v1', name: 'Forvis Mazars AI' },
  ];

  it('resolves a namespaced id or a bare stem', () => {
    expect(templateDisplayName('forvis-mazars/fm-slides-v1', catalog)).toBe('Forvis Mazars AI');
    expect(templateDisplayName('fm-slides-v1', catalog)).toBe('Forvis Mazars AI');
  });

  it('omits unknown or empty ids instead of inventing a name', () => {
    expect(templateDisplayName('missing', catalog)).toBeNull();
    expect(templateDisplayName('', catalog)).toBeNull();
    expect(templateDisplayName(null, catalog)).toBeNull();
  });
});
