import { readdirSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { KIT_CATALOG, PLATFORM_THEME_PATH, themeSections } from './theme-model';

const UI_DIR = path.resolve(__dirname, '../../../components/ui');

describe('the Theme page', () => {
  it('lives under Platform Settings', () => {
    expect(PLATFORM_THEME_PATH).toBe('/settings/theme');
  });

  it('shows every module of the kit, so nobody rebuilds one that exists', () => {
    const modules = readdirSync(UI_DIR)
      .filter((name) => name.endsWith('.tsx') && !name.includes('.test.'))
      .map((name) => name.replace(/\.tsx$/, ''))
      .sort();
    expect([...new Set(KIT_CATALOG.map((entry) => entry.module))].sort()).toEqual(modules);
  });

  it('groups entries by section, each section once, in catalog order', () => {
    const ids = themeSections().map((section) => section.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids[0]).toBe('buttons');
    expect(themeSections().find((s) => s.id === 'fields')?.entries.map((e) => e.module)).toEqual([
      'input',
      'checkbox',
      'field',
    ]);
  });
});
