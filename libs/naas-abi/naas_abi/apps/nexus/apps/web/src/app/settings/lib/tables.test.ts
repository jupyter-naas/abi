import { describe, expect, it } from 'vitest';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';
import {
  isPlatformTable,
  LEGACY_WORKSPACE_SETTINGS_SLUGS,
  PLATFORM_TABLE_SECTIONS,
  PLATFORM_TABLE_SLUGS,
  PLATFORM_TABLES,
  platformTableFromSlug,
  platformTableLabel,
  platformTableSection,
  platformTableSlug,
  platformRowId,
  platformRowPath,
} from './tables';

describe('platform tables', () => {
  it('lists the tables the API serves', () => {
    // Keep in sync with PLATFORM_TABLES in api/app/core/platform_tables.py.
    expect(PLATFORM_TABLES).toHaveLength(38);
    expect(PLATFORM_TABLE_SECTIONS.map((section) => [section.label, section.tables.length])).toEqual([
      ['People & access', 7],
      ['Sign-in & security', 9],
      ['Chat, agents & models', 8],
      ['Apps', 1],
      ['Code', 1],
      ['Maps', 5],
      ['Graph', 3],
      ['Ontology', 2],
      ['Search', 2],
    ]);
    expect(new Set(PLATFORM_TABLES).size).toBe(PLATFORM_TABLES.length);
  });

  it('labels and sections tables, and falls back for unknown names', () => {
    expect(isPlatformTable('workspaces')).toBe(true);
    expect(isPlatformTable('members')).toBe(false);
    expect(platformTableLabel('organization_members')).toBe('Organization members');
    expect(platformTableLabel('other')).toBe('other');
    expect(platformTableSection('users')).toBe('People & access');
    expect(platformTableSection('search_topics')).toBe('Search');
    expect(platformTableSection('coding_environments')).toBe('Code');
    expect(platformTableSection('ontology_icons')).toBe('Ontology');
    expect(platformTableSection('other')).toBeNull();
  });
});

describe('table page slugs', () => {
  it('knows every legacy workspace settings path', () => {
    const workspaceSlugs = SETTINGS_GROUPS.flatMap((group) => group.items).map((item) =>
      item.href.replace(/^\/settings\//, '')
    );
    expect([...LEGACY_WORKSPACE_SETTINGS_SLUGS].sort()).toEqual([...workspaceSlugs].sort());
  });

  it('never gives a table page a legacy workspace settings path', () => {
    for (const slug of PLATFORM_TABLE_SLUGS) {
      expect(LEGACY_WORKSPACE_SETTINGS_SLUGS).not.toContain(slug);
    }
    expect(platformTableSlug('secrets')).toBe('secrets_table');
    expect(platformTableSlug('ontologies')).toBe('ontologies_table');
    expect(platformTableSlug('workspace_members')).toBe('workspace_members');
    // The two tables named like a legacy path get the suffix.
    expect(PLATFORM_TABLE_SLUGS).toContain('secrets_table');
    expect(PLATFORM_TABLE_SLUGS).toContain('ontologies_table');
  });

  it('maps slugs back to tables', () => {
    expect(platformTableFromSlug('users')).toBe('users');
    expect(platformTableFromSlug('members')).toBeNull();
    expect(platformTableFromSlug('nope')).toBeNull();
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

  it('builds row paths under the table slug', () => {
    expect(platformRowPath('users', 'user-48f0f9a98e27')).toBe('/settings/users/user-48f0f9a98e27');
    expect(platformRowPath('secrets', 'a/b')).toBe('/settings/secrets_table/a%2Fb');
  });
});
