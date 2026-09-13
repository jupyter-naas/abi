import { describe, expect, it } from 'vitest';

import { DEFAULT_DOCUMENTS_TEMPLATE_ID } from './create-documents-project';
import {
  DEFAULT_TEMPLATE_PREVIEW,
  SLIDES_HOME_BLANK_TEMPLATE_ID,
  resolveDocumentsTemplateId,
  sectionsHomeTemplateCards,
  sectionsTemplateMenuRows,
  templateAssetLabel,
  templateDisplayName,
  templateNamespace,
  templateNamespaceLabel,
  templatePreviewColors,
  templateSectionLabel,
  templateNamespacesAreAmbiguous,
} from './documents-templates';

describe('templateSectionLabel', () => {
  it('joins eyebrow and title', () => {
    expect(templateSectionLabel({ eyebrow: 'Agenda', title: 'What we will cover' })).toBe(
      'Agenda: What we will cover',
    );
  });

  it('uses title when eyebrow matches', () => {
    expect(templateSectionLabel({ eyebrow: 'Context', title: 'Context' })).toBe('Context');
  });

  it('falls back to untitled', () => {
    expect(templateSectionLabel({ eyebrow: '', title: '' })).toBe('Untitled section');
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
    expect(templateNamespaceLabel('acme')).toBe('Acme');
  });

  it('title-cases an unknown slug', () => {
    expect(templateNamespaceLabel('acme-house')).toBe('Acme House');
  });
});

describe('resolveDocumentsTemplateId', () => {
  it('prefers an explicit pick', () => {
    expect(
      resolveDocumentsTemplateId(
        [{ id: DEFAULT_DOCUMENTS_TEMPLATE_ID, is_default: true }],
        'acme/house-v1',
      ),
    ).toBe('acme/house-v1');
  });

  it('uses the flagged default when the catalog hid ABI\'s seed', () => {
    expect(
      resolveDocumentsTemplateId([
        { id: 'acme/house-v1', is_default: true },
        { id: 'acme/memo-v1' },
      ]),
    ).toBe('acme/house-v1');
  });

  it('falls back to ABI\'s seed when it is still in the catalog', () => {
    expect(
      resolveDocumentsTemplateId([
        { id: DEFAULT_DOCUMENTS_TEMPLATE_ID },
        { id: 'acme/house-v1' },
      ]),
    ).toBe(DEFAULT_DOCUMENTS_TEMPLATE_ID);
  });
});

describe('sectionsHomeTemplateCards', () => {
  it('pins Blank to the default seed even when the catalog is empty', () => {
    expect(sectionsHomeTemplateCards([])).toEqual([
      { id: DEFAULT_DOCUMENTS_TEMPLATE_ID, label: 'Blank', blank: true },
    ]);
    expect(SLIDES_HOME_BLANK_TEMPLATE_ID).toBe(DEFAULT_DOCUMENTS_TEMPLATE_ID);
  });

  it('puts Blank first when ABI\'s seed is still in the catalog', () => {
    const cards = sectionsHomeTemplateCards([
      { id: 'acme/industry-v2', name: 'Industry' },
      { id: DEFAULT_DOCUMENTS_TEMPLATE_ID, name: 'Article Light' },
      { id: 'acme/memo-v1', name: 'Memo' },
    ]);
    expect(cards.map((card) => card.label)).toEqual(['Blank', 'Industry', 'Memo']);
    expect(cards[0]?.id).toBe(DEFAULT_DOCUMENTS_TEMPLATE_ID);
    expect(cards[1]?.id).toBe('acme/industry-v2');
    expect(cards.every((card) => !card.label.includes('/'))).toBe(true);
  });

  it('does not invent a Blank card when ABI\'s seed is absent', () => {
    const cards = sectionsHomeTemplateCards([
      { id: 'acme/industry-v2', name: 'Industry' },
      { id: 'acme/memo-v1', name: 'Memo' },
    ]);
    expect(cards.map((card) => card.label)).toEqual(['Industry', 'Memo']);
  });
});

describe('sectionsTemplateMenuRows', () => {
  it('lists names only when every seed is from one source', () => {
    const rows = sectionsTemplateMenuRows([
      { id: 'abi/minimal-light-v1', source: 'abi', name: 'Minimal Light', preview_accent: '#111' },
      { id: 'abi/pitch-dark-v1', source: 'abi', name: 'Pitch Dark', preview_accent: '#222' },
    ]);
    expect(rows).toEqual([
      { kind: 'template', id: 'abi/minimal-light-v1', label: 'Minimal Light', swatch: '#111' },
      { kind: 'template', id: 'abi/pitch-dark-v1', label: 'Pitch Dark', swatch: '#222' },
    ]);
  });

  it('inserts source headings instead of prefixing each row', () => {
    const rows = sectionsTemplateMenuRows([
      { id: 'abi/minimal-light-v1', source: 'abi', name: 'Minimal Light' },
      {
        id: 'acme/industry-v2',
        source: 'acme',
        name: 'Industry',
      },
    ]);
    expect(rows.map((row) => row.label)).toEqual([
      'ABI',
      'Minimal Light',
      'Acme',
      'Industry',
    ]);
    expect(rows.every((row) => !row.label.includes('/'))).toBe(true);
    expect(rows.find((row) => row.kind === 'template' && row.label === 'Industry')?.id).toBe(
      'acme/industry-v2',
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
    { id: 'acme/industry-v2', name: 'Industry' },
  ];

  it('resolves a namespaced id or a bare stem', () => {
    expect(templateDisplayName('acme/industry-v2', catalog)).toBe('Industry');
    expect(templateDisplayName('industry-v2', catalog)).toBe('Industry');
  });

  it('omits unknown or empty ids instead of inventing a name', () => {
    expect(templateDisplayName('missing', catalog)).toBeNull();
    expect(templateDisplayName('', catalog)).toBeNull();
    expect(templateDisplayName(null, catalog)).toBeNull();
  });
});
