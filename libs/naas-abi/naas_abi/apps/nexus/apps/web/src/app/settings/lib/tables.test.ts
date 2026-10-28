import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';
import {
  LEGACY_WORKSPACE_SETTINGS_SLUGS,
  PLATFORM_TABLES_PATH,
  platformRowId,
  platformRowPath,
  platformTablePath,
  tableFromLegacySlug,
} from './tables';

const SETTINGS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
const WORKSPACE_SETTINGS_DIR = join(SETTINGS_DIR, '..', 'workspace', '[workspaceId]', 'settings');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe('the table list', () => {
  it('comes from the API: Platform Settings keeps no copy of it', () => {
    // The registry is core/platform_tables.py, served by GET /api/admin/tables.
    const page = readFileSync(join(SETTINGS_DIR, 'tables', 'page.tsx'), 'utf8');
    expect(page).toContain("authFetch('/api/admin/tables')");
    // No table name is spelled out in the settings code.
    for (const file of sources(SETTINGS_DIR)) {
      const text = readFileSync(file, 'utf8');
      for (const table of ['organization_members', 'workspace_resource_policies', 'auth_sessions']) {
        expect(text.includes(`'${table}'`), `${file} names ${table}`).toBe(false);
      }
    }
  });
});

describe('table paths', () => {
  it('puts every table under /settings/tables', () => {
    expect(PLATFORM_TABLES_PATH).toBe('/settings/tables');
    expect(platformTablePath('users')).toBe('/settings/tables/users');
    expect(platformTablePath('secrets')).toBe('/settings/tables/secrets');
  });

  it('turns an old table slug back into its table', () => {
    expect(tableFromLegacySlug('users')).toBe('users');
    expect(tableFromLegacySlug('secrets_table')).toBe('secrets');
    expect(tableFromLegacySlug('ontologies_table')).toBe('ontologies');
    // Only a legacy workspace path took the suffix.
    expect(tableFromLegacySlug('users_table')).toBe('users_table');
  });

  it('knows every workspace settings page, so its bare link still goes to the workspace', () => {
    const pages = readdirSync(WORKSPACE_SETTINGS_DIR).filter((name) =>
      statSync(join(WORKSPACE_SETTINGS_DIR, name)).isDirectory()
    );
    expect(pages).toContain('infrastructure');
    for (const page of pages) expect(LEGACY_WORKSPACE_SETTINGS_SLUGS).toContain(page);
  });

  it('knows every legacy workspace settings path', () => {
    const workspaceSlugs = SETTINGS_GROUPS.flatMap((group) => group.items).map((item) =>
      item.href.replace(/^\/settings\//, '')
    );
    for (const slug of workspaceSlugs) expect(LEGACY_WORKSPACE_SETTINGS_SLUGS).toContain(slug);
  });
});

describe('row pages', () => {
  it('uses the primary key as the row id', () => {
    expect(platformRowId({ id: 'user-48f0f9a98e27', email: 'a@b.c' }, ['id'])).toBe(
      'user-48f0f9a98e27'
    );
    expect(
      platformRowId({ workspace_id: 'ws-1', resource_kind: 'maps' }, ['workspace_id', 'resource_kind'])
    ).toBe('ws-1~maps');
    expect(platformRowId({ id: 'x' }, [])).toBeNull();
  });

  it('builds row paths under the table', () => {
    expect(platformRowPath('users', 'user-48f0f9a98e27')).toBe(
      '/settings/tables/users/user-48f0f9a98e27'
    );
    expect(platformRowPath('secrets', 'a/b')).toBe('/settings/tables/secrets/a%2Fb');
  });
});
