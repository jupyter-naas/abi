import { describe, expect, it } from 'vitest';
import { viewFor } from '../system/data/services/registry';
import { SERVICE_ICONS } from './nav';
import { SERVICE_PAGES, serviceForPage, servicePagePath, servicePagesIn } from './service-pages';

// What GET /api/sysadmin/resources lists (services/sysadmin/factory.py build_resource_admin).
const API_SERVICES = [
  'activity_log',
  'bus',
  'cache',
  'coding_environment',
  'dataset',
  'discovery',
  'document',
  'email',
  'event',
  'keyvalue',
  'model_registry',
  'object_storage',
  'secret',
  'source_control',
  'triple_store',
  'vector_store',
];

describe('service pages', () => {
  it('give every service of the API one page', () => {
    expect(SERVICE_PAGES.map((page) => page.service).sort()).toEqual(API_SERVICES);
    expect(new Set(SERVICE_PAGES.map((page) => servicePagePath(page.service))).size).toBe(SERVICE_PAGES.length);
  });

  it('name and draw each page as its service view does', () => {
    for (const page of SERVICE_PAGES) {
      const view = viewFor(page.service);
      expect([page.service, page.label]).toEqual([page.service, view.label]);
      expect(SERVICE_ICONS[page.service]).toBe(view.icon);
    }
  });

  it('put each service under the question it answers', () => {
    expect(servicePagesIn('system').map((page) => page.service)).toEqual(['discovery', 'bus']);
    expect(servicePagesIn('activity').map((page) => page.service)).toEqual(['event', 'activity_log']);
    expect(servicePagesIn('resources').map((page) => page.service)).toEqual([
      'model_registry',
      'secret',
      'email',
      'source_control',
      'coding_environment',
    ]);
    expect(servicePagesIn('data').map((page) => page.service)).toEqual([
      'triple_store',
      'vector_store',
      'document',
      'dataset',
      'object_storage',
      'keyvalue',
      'cache',
    ]);
  });

  it('find the service of a page, and only in its own section', () => {
    expect(servicePagePath('triple_store')).toBe('/settings/data/knowledge-graph');
    expect(serviceForPage('data', 'knowledge-graph')).toBe('triple_store');
    expect(serviceForPage('resources', 'models')).toBe('model_registry');
    expect(serviceForPage('resources', 'knowledge-graph')).toBeNull();
    expect(serviceForPage('resources', 'nope')).toBeNull();
  });

  it('open a service without a page of its own under Data, by its API name', () => {
    expect(servicePagePath('new_store')).toBe('/settings/data/new_store');
    expect(serviceForPage('data', 'new_store')).toBe('new_store');
    expect(serviceForPage('data', 'a%2Fb')).toBe('a/b');
    // A known service has its page: its API name is no alias of it.
    expect(serviceForPage('data', 'model_registry')).toBeNull();
    expect(serviceForPage('data', 'models')).toBeNull();
    expect(serviceForPage('data', '')).toBeNull();
  });
});
