import { describe, expect, it } from 'vitest';
import { buildJsonExport, buildWorkbookSheets, mapWithLimit, type ExportedTable } from './export-all';

const users: ExportedTable = {
  name: 'users',
  description: 'Accounts',
  columns: ['id', 'hashed_password', 'is_superadmin', 'bio'],
  rows: [{ id: 'u-1', hashed_password: '••••••', is_superadmin: true, bio: null }],
  total: 1,
  truncated: false,
};
const empty: ExportedTable = {
  name: 'api_keys',
  description: 'Keys',
  columns: ['id', 'key_hash'],
  rows: [],
  total: 0,
  truncated: false,
};

describe('buildJsonExport', () => {
  it('keys tables by name and keeps rows as served (masked)', () => {
    const json = buildJsonExport([users, empty], new Date('2026-10-14T12:00:00Z'));
    expect(json.exported_at).toBe('2026-10-14T12:00:00.000Z');
    expect(Object.keys(json.tables)).toEqual(['users', 'api_keys']);
    expect(json.tables.users.rows[0].hashed_password).toBe('••••••');
    expect(json.tables.api_keys).toMatchObject({ columns: ['id', 'key_hash'], rows: [] });
  });
});

describe('buildWorkbookSheets', () => {
  it('writes one sheet per table, empty tables keep their headers', () => {
    expect(buildWorkbookSheets([users, empty])).toEqual([
      {
        name: 'users',
        headers: ['id', 'hashed_password', 'is_superadmin', 'bio'],
        rows: [['u-1', '••••••', 'true', 'NULL']],
      },
      { name: 'api_keys', headers: ['id', 'key_hash'], rows: [] },
    ]);
  });
});

describe('mapWithLimit', () => {
  it('keeps order and never runs more than the limit at once', async () => {
    let running = 0;
    let peak = 0;
    const out = await mapWithLimit([1, 2, 3, 4, 5], 2, async (n) => {
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((resolve) => setTimeout(resolve, 5));
      running -= 1;
      return n * 10;
    });
    expect(out).toEqual([10, 20, 30, 40, 50]);
    expect(peak).toBe(2);
  });
});
