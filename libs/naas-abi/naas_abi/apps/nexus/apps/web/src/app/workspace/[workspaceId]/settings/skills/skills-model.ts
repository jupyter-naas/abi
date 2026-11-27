/**
 * Settings › Skills: the columns of its table (search, sort, filter, export, as Settings › Users).
 * Pure: the view is `page.tsx`.
 */
import type { Skill, SkillScope } from '@/stores/skills';

export const SCOPE_LABELS: Record<SkillScope, string> = {
  user: 'Private',
  workspace: 'Workspace',
  organization: 'Organization',
};

export type SkillColumnId = 'skill' | 'command' | 'visibility' | 'lastUsed' | 'enabled';
export const SKILL_COLUMNS: { id: SkillColumnId; label: string; className?: string }[] = [
  { id: 'skill', label: 'Skill' },
  { id: 'command', label: 'Command' },
  { id: 'visibility', label: 'Visibility' },
  { id: 'lastUsed', label: 'Last used' },
  { id: 'enabled', label: 'Enabled', className: 'w-24' },
];

/** The day a skill was last used, as its row shows it; empty when never. */
export function lastUsedDay(skill: Skill): string {
  return skill.lastUsedAt ? new Date(skill.lastUsedAt).toLocaleDateString() : '';
}

/** What a column filter sees of a row. */
export function skillCellValues(skill: Skill, column: SkillColumnId): string[] {
  if (column === 'skill') return [skill.name];
  if (column === 'command') return [`/${skill.slug}`];
  if (column === 'visibility') return [SCOPE_LABELS[skill.scope]];
  if (column === 'lastUsed') return [lastUsedDay(skill) || 'Never'];
  return [skill.enabled ? 'Enabled' : 'Disabled'];
}

/** What a column sorts on: Last used by time (never first), the others by their cell. */
export function skillSortValue(skill: Skill, column: SkillColumnId): string | number {
  if (column === 'lastUsed') return skill.lastUsedAt ? Date.parse(skill.lastUsedAt) : 0;
  return skillCellValues(skill, column).join(', ');
}

/** What the search bar reads of a row: name, slug, description, visibility and status. */
export function skillSearchTexts(skill: Skill): string[] {
  return [
    skill.name,
    skill.slug,
    skill.description,
    SCOPE_LABELS[skill.scope],
    skill.enabled ? 'Enabled' : 'Disabled',
  ];
}

export const SKILL_EXPORT_HEADERS = ['Skill', 'Command', 'Description', 'Visibility', 'Last used', 'Enabled'];

/** A row of the CSV / Excel export, as the table shows it. */
export function skillExportRow(skill: Skill): string[] {
  return [
    skill.name,
    `/${skill.slug}`,
    skill.description,
    SCOPE_LABELS[skill.scope],
    lastUsedDay(skill),
    skill.enabled ? 'Yes' : 'No',
  ];
}
