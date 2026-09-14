import { describe, expect, it } from 'vitest';

import {
  officeCreateHref,
  officeCreateStatus,
  officeCreateTemplateId,
} from './office-create';

describe('officeCreateHref', () => {
  it('opens the Documents new route immediately', () => {
    expect(officeCreateHref('document', 'ws-1')).toBe('/workspace/ws-1/documents/new');
  });

  it('opens the Slides new route immediately', () => {
    expect(officeCreateHref('deck', 'ws-1')).toBe('/workspace/ws-1/slides/new');
  });

  it('carries a template on the query string', () => {
    expect(officeCreateHref('document', 'ws-1', 'abi/article-light-v1')).toBe(
      '/workspace/ws-1/documents/new?template=abi%2Farticle-light-v1',
    );
  });

  it('ignores a blank template', () => {
    expect(officeCreateHref('deck', 'ws-1', '  ')).toBe('/workspace/ws-1/slides/new');
  });
});

describe('officeCreateTemplateId', () => {
  it('reads a template query', () => {
    expect(
      officeCreateTemplateId({ get: (key) => (key === 'template' ? 'abi/minimal-light-v1' : null) }),
    ).toBe('abi/minimal-light-v1');
  });

  it('treats a missing or blank template as unset', () => {
    expect(officeCreateTemplateId({ get: () => null })).toBeUndefined();
    expect(officeCreateTemplateId({ get: () => '  ' })).toBeUndefined();
    expect(officeCreateTemplateId(null)).toBeUndefined();
  });
});

describe('officeCreateStatus', () => {
  it('names the workspace wait first, then the surface', () => {
    expect(officeCreateStatus('document', 'creating')).toBe('Creating workspace…');
    expect(officeCreateStatus('deck', 'creating')).toBe('Creating workspace…');
    expect(officeCreateStatus('document', 'opening')).toBe('Opening document…');
    expect(officeCreateStatus('deck', 'opening')).toBe('Opening presentation…');
  });
});
