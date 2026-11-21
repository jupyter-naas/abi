// "Superadmin" is "Platform admin" in every user-facing string (ADR
// `20261120_access_levels_and_groups`): IAM's name for it. Internal names (`is_superadmin`,
// `useSuperadminAccess`, a column id) stay.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '..', '..');


function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sources(full);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [full] : [];
  });
}

/** The code without its comments (a comment is no user-facing string). */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

/** "superadmin" or "super admin" as words people read: not an identifier, an object key, a
 *  property, or a quoted id (`'superadmin'`, `data-action="superadmin"`). */
export function userFacing(text: string): string[] {
  const found: string[] = [];
  const pattern = /(?<![A-Za-z0-9_\-.])(super ?admins?)(?![A-Za-z0-9_])/gi;
  for (const match of text.matchAll(pattern)) {
    const before = text[match.index! - 1] ?? '';
    const after = text[match.index! + match[0].length] ?? '';
    if (after === ':' || (before === after && `'"\``.includes(before))) continue;
    const line = text.slice(text.lastIndexOf('\n', match.index!) + 1, text.indexOf('\n', match.index!));
    found.push(line.trim());
  }
  return found;
}

describe('the platform admin’s name', () => {
  it('tells a word from an identifier', () => {
    expect(userFacing("title: 'Remove superadmin access'")).toHaveLength(1);
    expect(userFacing('<p>Superadmins reach Platform Settings</p>')).toHaveLength(1);
    expect(userFacing("data-action=\"superadmin\" is_superadmin isSuperadmin useSuperadminAccess { superadmin: true } data.superadmin 'superadmin'")).toEqual([]);
  });

  it('is never "superadmin" where people read it', () => {
    const offenders = sources(SRC)
      .flatMap((file) => userFacing(withoutComments(readFileSync(file, 'utf8'))).map((line) => `${path.relative(SRC, file)}: ${line}`));
    expect(offenders).toEqual([]);
  });
});
