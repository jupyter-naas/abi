import { describe, expect, it } from 'vitest';

import {
  SKILL_MD_PATH,
  addSkillDraftFile,
  initialSkillDraftFiles,
  removeSkillDraftFile,
} from './skill-draft-files';

describe('skill draft files', () => {
  it('starts with SKILL.md', () => {
    expect(initialSkillDraftFiles()).toEqual([{ path: SKILL_MD_PATH, body: '' }]);
  });

  it('add file appends a path', () => {
    const next = addSkillDraftFile(initialSkillDraftFiles(), 'references/notes.md');
    expect(next.map((file) => file.path)).toEqual(['SKILL.md', 'references/notes.md']);
    expect(next[1]?.body).toBe('');
  });

  it('remove cannot drop SKILL.md', () => {
    const withExtra = addSkillDraftFile(initialSkillDraftFiles(), 'references/notes.md');
    expect(removeSkillDraftFile(withExtra, SKILL_MD_PATH).map((file) => file.path)).toEqual([
      'SKILL.md',
      'references/notes.md',
    ]);
    expect(removeSkillDraftFile(withExtra, 'references/notes.md').map((file) => file.path)).toEqual([
      'SKILL.md',
    ]);
  });

  it('rejects a parent directory path', () => {
    expect(() => addSkillDraftFile(initialSkillDraftFiles(), '../notes.md')).toThrow(/relative path/);
  });
});
