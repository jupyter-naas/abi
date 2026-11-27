import { describe, expect, it } from 'vitest';
import type { AppItem } from '@/stores/apps';
import {
  APP_EXPORT_HEADERS,
  appCellValues,
  appExportRow,
  appSearchTexts,
  appSource,
  installedApps,
} from './apps-model';

const app = (over: Partial<AppItem>): AppItem => ({
  module_path: 'acme.apps',
  app_name: 'crm',
  app_id: 'crm',
  category: 'core',
  name: 'CRM',
  description: 'Clients and deals',
  url: 'https://apps.example/crm',
  installed: true,
  ...over,
});

describe('the apps table', () => {
  it('lists the installed apps with a URL', () => {
    const apps = [app({}), app({ app_id: 'off', installed: false }), app({ app_id: 'nourl', url: null })];
    expect(installedApps(apps).map((a) => a.app_id)).toEqual(['crm']);
  });

  it('reads the source from the maintainer, else the module', () => {
    expect(appSource(app({ maintainer: 'Acme' }))).toBe('Acme');
    expect(appSource(app({ module_name: 'CRM module' }))).toBe('CRM module');
    expect(appSource(app({}))).toBe('acme.apps');
  });

  it('gives each column the values its filter sees, and the search its texts', () => {
    const crm = app({ maintainer: 'Acme' });
    expect(appCellValues(crm, 'app')).toEqual(['CRM']);
    expect(appCellValues(crm, 'category')).toEqual(['core']);
    expect(appCellValues(crm, 'source')).toEqual(['Acme']);
    expect(appSearchTexts(crm)).toEqual(['CRM', 'Clients and deals', 'core', 'Acme']);
  });

  it('exports a row as the table shows it, with its URL', () => {
    expect(APP_EXPORT_HEADERS).toEqual(['App', 'Description', 'Category', 'Source', 'URL']);
    expect(appExportRow(app({}))).toEqual(['CRM', 'Clients and deals', 'core', 'acme.apps', 'https://apps.example/crm']);
  });
});
