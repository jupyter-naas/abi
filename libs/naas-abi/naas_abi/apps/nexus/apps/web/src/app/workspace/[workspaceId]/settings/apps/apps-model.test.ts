import { describe, expect, it } from 'vitest';
import type { AppItem } from '@/stores/apps';
import {
  APP_EXPORT_HEADERS,
  appCellValues,
  appExportRow,
  appSearchTexts,
  appRows,
  appScope,
  appSource,
  installedApps,
} from './apps-model';
import type { ModuleItem } from '@/components/settings/module-items-model';

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
    expect(APP_EXPORT_HEADERS).toEqual(['App', 'Description', 'Category', 'Source', 'URL', 'Enabled']);
    expect(appExportRow(app({}))).toEqual([
      'CRM',
      'Clients and deals',
      'core',
      'acme.apps',
      'https://apps.example/crm',
      'Enabled',
    ]);
  });
});

describe('the apps table and the module items', () => {
  const item = (module: string, name: string, offered: boolean): ModuleItem => ({
    kind: 'apps',
    module,
    name,
    label: name.toUpperCase(),
    offered,
    grantable: true,
  });

  it('reads the module item an app id names', () => {
    expect(appScope('acme.apps:crm')).toEqual({ module: 'acme.apps', name: 'crm' });
    expect(appScope('remote/acme.remote:board')).toEqual({ module: 'acme.remote', name: 'board' });
    expect(appScope('crm')).toBeNull();
  });

  it('lists every module app: those the caller opens keep their row, the others get one', () => {
    const rows = appRows(
      [app({ app_id: 'acme.apps:crm' }), app({ app_id: 'acme.apps:wiki', installed: false })],
      [item('acme.apps', 'crm', true), item('acme.apps', 'wiki', false)],
    );
    expect(rows.map((row) => [row.key, row.listed, row.item?.name])).toEqual([
      ['acme.apps:crm', true, 'crm'],
      ['apps|acme.apps|wiki', false, 'wiki'],
    ]);
    const wiki = rows[1];
    expect(appCellValues(wiki, 'app')).toEqual(['WIKI']);
    expect(appCellValues(wiki, 'category')).toEqual([]);
    expect(appCellValues(wiki, 'source')).toEqual(['acme.apps']);
    expect(appCellValues(wiki, 'enabled')).toEqual(['Disabled']);
    expect(appCellValues(rows[0], 'enabled')).toEqual(['Enabled']);
  });
});
