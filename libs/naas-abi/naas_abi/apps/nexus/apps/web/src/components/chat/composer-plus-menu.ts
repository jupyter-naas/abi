/** Rows for the chat composer "+" menu. */

export const COMPOSER_PLUS_FILES_LABEL = 'Add files';
export const COMPOSER_PLUS_SKILLS_LABEL = 'Skills';
export const COMPOSER_PLUS_MANAGE_SKILLS_LABEL = 'Manage skills';
export const COMPOSER_PLUS_LOADING_LABEL = 'Loading skills';

export type ComposerPlusSkillInput = {
  slug: string;
  name: string;
  description?: string;
  enabled: boolean;
  lastUsedAt?: string | null;
};

export type ComposerPlusSkillItem = {
  slug: string;
  name: string;
  description: string;
  /** Literal composer text. The client sends this; the server expands the slug. */
  insertText: string;
};

export type ComposerPlusManageSkills = {
  label: typeof COMPOSER_PLUS_MANAGE_SKILLS_LABEL;
  /** Settings list. This row navigates; it does not insert a slash command. */
  href: string;
};

export type ComposerPlusRow =
  | { id: 'files'; kind: 'files'; label: typeof COMPOSER_PLUS_FILES_LABEL }
  | {
      id: 'skills';
      kind: 'skills';
      label: typeof COMPOSER_PLUS_SKILLS_LABEL;
      skills: ComposerPlusSkillItem[];
      /** Present when a workspace can host the settings page. Last submenu row. */
      manage: ComposerPlusManageSkills | null;
    }
  | {
      id: 'skills';
      kind: 'skills-loading';
      label: typeof COMPOSER_PLUS_SKILLS_LABEL;
      hint: typeof COMPOSER_PLUS_LOADING_LABEL;
    };

const usedAt = (value?: string | null): number => {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
};

/** Default composer hint. Images, files, and open office surfaces keep their own copy. */
export function chatComposerPlaceholder(input: {
  hasImages: boolean;
  hasFiles: boolean;
  onSlides: boolean;
  onDocuments: boolean;
}): string {
  if (input.hasImages) return 'Ask about the image...';
  if (input.hasFiles) return 'Ask about the file...';
  if (input.onSlides) return 'Describe the deck: topic, audience, how many slides...';
  if (input.onDocuments) return 'Describe the document: topic, audience...';
  return 'Message';
}

/** `/slug ` with a trailing space, matching slash completion. */
export function skillCommandText(slug: string): string {
  return `/${slug} `;
}

/**
 * Composer value after a skill is chosen.
 * The message starts with `/slug ` so the server can expand it.
 * Text already in the box is kept as arguments.
 */
export function composerTextWithSkill(current: string, slug: string): string {
  const command = skillCommandText(slug);
  const withoutCommand = current.replace(/^\s*\/[a-zA-Z0-9][a-zA-Z0-9_-]*\s*/, '');
  const args = withoutCommand.trim();
  return args ? `${command}${args}` : command;
}

/** Skills settings list. Add Skill lives on that page. */
export function manageSkillsSettingsHref(workspaceId: string): string {
  return `/workspace/${workspaceId}/settings/skills`;
}

/** Enabled skills, same order as slash autocomplete: recent use, then slug. */
export function invocableComposerSkills(
  skills: ComposerPlusSkillInput[],
): ComposerPlusSkillItem[] {
  return skills
    .filter((skill) => skill.enabled && skill.slug.trim().length > 0)
    .sort((a, b) => {
      const used = usedAt(b.lastUsedAt) - usedAt(a.lastUsedAt);
      if (used !== 0) return used;
      return a.slug.localeCompare(b.slug);
    })
    .map((skill) => ({
      slug: skill.slug,
      name: skill.name,
      description: skill.description ?? '',
      insertText: skillCommandText(skill.slug),
    }));
}

/**
 * Menu rows the composer can actually perform.
 * Files first. Skills second, when the skills feature is on.
 * Web search, projects, memory, connectors, plugins, and research are omitted:
 * the composer has no control for them.
 */
export function composerPlusMenuRows(input: {
  skills: ComposerPlusSkillInput[] | null;
  workspaceId: string | null;
  skillsEnabled?: boolean;
}): ComposerPlusRow[] {
  const rows: ComposerPlusRow[] = [
    { id: 'files', kind: 'files', label: COMPOSER_PLUS_FILES_LABEL },
  ];
  if (input.skillsEnabled === false) return rows;

  if (input.skills === null) {
    rows.push({
      id: 'skills',
      kind: 'skills-loading',
      label: COMPOSER_PLUS_SKILLS_LABEL,
      hint: COMPOSER_PLUS_LOADING_LABEL,
    });
    return rows;
  }

  const skills = invocableComposerSkills(input.skills);
  const manage: ComposerPlusManageSkills | null = input.workspaceId
    ? {
        label: COMPOSER_PLUS_MANAGE_SKILLS_LABEL,
        href: manageSkillsSettingsHref(input.workspaceId),
      }
    : null;
  // Submenu even when nothing is enabled, so Manage skills stays reachable.
  // With no workspace there is nowhere to send that row, and no commands to list.
  if (skills.length === 0 && !manage) return rows;

  rows.push({
    id: 'skills',
    kind: 'skills',
    label: COMPOSER_PLUS_SKILLS_LABEL,
    skills,
    manage,
  });
  return rows;
}
