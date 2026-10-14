import { describe, expect, it } from 'vitest';

import {
  COMPOSER_PLUS_FILES_LABEL,
  COMPOSER_PLUS_LOADING_LABEL,
  COMPOSER_PLUS_MANAGE_SKILLS_LABEL,
  COMPOSER_PLUS_SKILLS_LABEL,
  chatComposerPlaceholder,
  composerPlusMenuRows,
  composerTextWithSkill,
  skillCommandText,
} from './composer-plus-menu';

const briefing = {
  slug: 'briefing',
  name: 'Briefing',
  description: 'Write a short briefing',
  enabled: true,
  lastUsedAt: '2026-01-01T00:00:00.000Z',
};

const digest = {
  slug: 'digest',
  name: 'Digest',
  description: 'Summarize the week',
  enabled: true,
  lastUsedAt: '2026-02-01T00:00:00.000Z',
};

describe('composerPlusMenuRows', () => {
  it('opens with Add files and a skills submenu of enabled commands', () => {
    const rows = composerPlusMenuRows({
      workspaceId: 'ws-1',
      skills: [
        briefing,
        digest,
        { ...briefing, slug: 'retired', name: 'Retired', enabled: false },
      ],
    });

    expect(rows.map((row) => row.id)).toEqual(['files', 'skills']);
    expect(rows[0]).toEqual({
      id: 'files',
      kind: 'files',
      label: COMPOSER_PLUS_FILES_LABEL,
    });
    expect(rows[1]).toMatchObject({
      id: 'skills',
      kind: 'skills',
      label: COMPOSER_PLUS_SKILLS_LABEL,
    });
    if (rows[1]?.kind !== 'skills') throw new Error('expected skills submenu');
    expect(rows[1].skills.map((skill) => skill.slug)).toEqual(['digest', 'briefing']);
    expect(rows[1].skills[0]?.insertText).toBe('/digest ');
    expect(rows[1].skills.some((skill) => skill.insertText.startsWith('/manage'))).toBe(false);
    expect(rows[1].manage).toEqual({
      label: COMPOSER_PLUS_MANAGE_SKILLS_LABEL,
      href: '/workspace/ws-1/settings/skills',
    });
    expect(rows.map((row) => row.kind)).toEqual(['files', 'skills']);
  });

  it('opens the skills submenu on Manage skills when none are enabled', () => {
    const rows = composerPlusMenuRows({
      workspaceId: 'ws-1',
      skills: [{ ...briefing, enabled: false }],
    });

    expect(rows).toEqual([
      { id: 'files', kind: 'files', label: COMPOSER_PLUS_FILES_LABEL },
      {
        id: 'skills',
        kind: 'skills',
        label: COMPOSER_PLUS_SKILLS_LABEL,
        skills: [],
        manage: {
          label: COMPOSER_PLUS_MANAGE_SKILLS_LABEL,
          href: '/workspace/ws-1/settings/skills',
        },
      },
    ]);
  });

  it('waits to offer create while the skill list is still loading', () => {
    const rows = composerPlusMenuRows({
      workspaceId: 'ws-1',
      skills: null,
    });

    expect(rows[1]).toEqual({
      id: 'skills',
      kind: 'skills-loading',
      label: COMPOSER_PLUS_SKILLS_LABEL,
      hint: COMPOSER_PLUS_LOADING_LABEL,
    });
  });

  it('omits Skills when the feature is off, and never invents other composer rows', () => {
    const rows = composerPlusMenuRows({
      workspaceId: 'ws-1',
      skills: [briefing],
      skillsEnabled: false,
    });

    expect(rows).toEqual([
      { id: 'files', kind: 'files', label: COMPOSER_PLUS_FILES_LABEL },
    ]);
    expect(rows.some((row) => /search|project|memory|connector|plugin|research/i.test(row.kind))).toBe(
      false,
    );
  });

  it('omits the skills submenu when there is no workspace and no commands', () => {
    expect(
      composerPlusMenuRows({ workspaceId: null, skills: [] }).map((row) => row.kind),
    ).toEqual(['files']);
  });

  it('lists commands without a manage row when there is no workspace', () => {
    const rows = composerPlusMenuRows({ workspaceId: null, skills: [briefing] });
    expect(rows[1]).toMatchObject({
      kind: 'skills',
      manage: null,
    });
  });
});

describe('chatComposerPlaceholder', () => {
  it('stays quiet when no file or office surface is open', () => {
    expect(
      chatComposerPlaceholder({
        hasImages: false,
        hasFiles: false,
        onSlides: false,
        onDocuments: false,
      }),
    ).toBe('Message');
  });
});

describe('composerTextWithSkill', () => {
  it('inserts the slash command the client already sends', () => {
    expect(skillCommandText('briefing')).toBe('/briefing ');
    expect(composerTextWithSkill('', 'briefing')).toBe('/briefing ');
    expect(composerTextWithSkill('   ', 'briefing')).toBe('/briefing ');
  });

  it('keeps typed text as arguments and replaces a previous command', () => {
    expect(composerTextWithSkill('for the board', 'briefing')).toBe('/briefing for the board');
    expect(composerTextWithSkill('/digest keep this', 'briefing')).toBe('/briefing keep this');
  });
});
