import { describe, expect, it } from 'vitest';
import { isImageHref, isMaterialIconValue, logoUrlProperties, materialIconName, normalizeImageHref } from './image-square';

describe('image square values', () => {
  it('accepts material icons and http image hrefs only', () => {
    expect(isMaterialIconValue('material-symbols-light:person-outline')).toBe(true);
    expect(isMaterialIconValue('material-symbols-light:Person')).toBe(false);
    expect(isImageHref('https://cdn.example/face.png')).toBe(true);
    expect(isImageHref('/uploads/object-images/a.png')).toBe(true);
    expect(isImageHref('/uploads/../secret.png')).toBe(false);
    expect(isImageHref('javascript:alert(1)')).toBe(false);
    expect(normalizeImageHref('  https://cdn.example/a.png  ')).toBe('https://cdn.example/a.png');
    expect(materialIconName('material-symbols-light:public')).toBe('public');
    expect(materialIconName('https://cdn.example/a.png')).toBeUndefined();
  });

  it('selects logo_url rows regardless of prefix', () => {
    const rows = logoUrlProperties([
      { predicate_uri: 'http://www.w3.org/2000/01/rdf-schema#label', value: 'Ada' },
      { predicate_uri: 'http://ontology.naas.ai/nexus/logo_url', value: 'https://cdn.example/a.png' },
      { predicate_uri: 'https://ontology.naas.ai/nexus/logo_url', value: 'https://cdn.example/b.png' },
    ]);
    expect(rows.map(row => row.value)).toEqual(['https://cdn.example/a.png', 'https://cdn.example/b.png']);
  });
});
