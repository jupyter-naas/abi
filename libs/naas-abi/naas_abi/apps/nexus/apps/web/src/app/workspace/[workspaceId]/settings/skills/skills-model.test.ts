import { describe, expect, it } from 'vitest';
import type { Skill } from '@/stores/skills';
import { skillCellValues, skillExportRow, skillSearchTexts, skillSortValue } from './skills-model';

function skill(over: Partial<Skill> & Pick<Skill, 'id' | 'name' | 'slug'>): Skill {
  return {
    workspaceId: 'ws-1',
    organizationId: null,
    userId: 'user-1',
    description: '',
    prompt: 'Do it',
    scope: 'workspace',
    enabled: true,
    lastUsedAt: null,
    createdAt: '2026-11-01T00:00:00Z',
    updatedAt: '2026-11-01T00:00:00Z',
    ...over,
  };
}

describe('the skills table (as Settings › Users)', () => {
  const report = skill({
    id: 's1',
    name: 'Weekly report',
    slug: 'weekly-report',
    description: 'Writes the weekly report',
    scope: 'user',
    lastUsedAt: '2026-11-20T10:00:00Z',
  });
  const draft = skill({ id: 's2', name: 'Draft', slug: 'draft', enabled: false });

  it('filters Visibility and Enabled on what a row shows, Never for a skill never used', () => {
    expect(skillCellValues(report, 'skill')).toEqual(['Weekly report']);
    expect(skillCellValues(report, 'command')).toEqual(['/weekly-report']);
    expect(skillCellValues(report, 'visibility')).toEqual(['Private']);
    expect(skillCellValues(draft, 'visibility')).toEqual(['Workspace']);
    expect(skillCellValues(report, 'enabled')).toEqual(['Enabled']);
    expect(skillCellValues(draft, 'enabled')).toEqual(['Disabled']);
    expect(skillCellValues(report, 'lastUsed')).toEqual([new Date('2026-11-20T10:00:00Z').toLocaleDateString()]);
    expect(skillCellValues(draft, 'lastUsed')).toEqual(['Never']);
  });

  it('sorts Last used by time, never used first', () => {
    expect(skillSortValue(draft, 'lastUsed')).toBe(0);
    expect(skillSortValue(report, 'lastUsed')).toBe(Date.parse('2026-11-20T10:00:00Z'));
    expect(skillSortValue(report, 'skill')).toBe('Weekly report');
  });

  it('searches the name, slug, description, visibility and status', () => {
    expect(skillSearchTexts(report)).toEqual([
      'Weekly report',
      'weekly-report',
      'Writes the weekly report',
      'Private',
      'Enabled',
    ]);
    expect(skillSearchTexts(draft)).toContain('Disabled');
  });

  it('exports a row as the table shows it', () => {
    expect(skillExportRow(draft)).toEqual(['Draft', '/draft', '', 'Workspace', '', 'No']);
    expect(skillExportRow(report)[5]).toBe('Yes');
  });
});
