/** Local files for a skill that has not been saved yet. */

export const SKILL_MD_PATH = 'SKILL.md';

export type SkillDraftFile = {
  path: string;
  body: string;
};

export function initialSkillDraftFiles(): SkillDraftFile[] {
  return [{ path: SKILL_MD_PATH, body: '' }];
}

/** A relative package path, or null when it would leave the skill directory. */
export function normalizeSkillDraftPath(raw: string): string | null {
  const trimmed = raw.trim().replace(/\\/g, '/');
  if (!trimmed || trimmed.startsWith('/') || trimmed.includes('\0')) return null;
  const parts = trimmed.split('/');
  if (parts.some((part) => part === '' || part === '.' || part === '..')) return null;
  return parts.join('/');
}

export function addSkillDraftFile(files: SkillDraftFile[], rawPath: string): SkillDraftFile[] {
  const path = normalizeSkillDraftPath(rawPath);
  if (!path) {
    throw new Error('Use a relative path inside the skill.');
  }
  if (files.some((file) => file.path.toLowerCase() === path.toLowerCase())) {
    throw new Error('That file is already in the skill.');
  }
  return [...files, { path, body: '' }];
}

export function removeSkillDraftFile(files: SkillDraftFile[], path: string): SkillDraftFile[] {
  if (path === SKILL_MD_PATH) return files;
  return files.filter((file) => file.path !== path);
}

export function updateSkillDraftFile(
  files: SkillDraftFile[],
  path: string,
  body: string,
): SkillDraftFile[] {
  return files.map((file) => (file.path === path ? { ...file, body } : file));
}

export function skillDraftBody(files: SkillDraftFile[], path: string): string {
  return files.find((file) => file.path === path)?.body ?? '';
}
