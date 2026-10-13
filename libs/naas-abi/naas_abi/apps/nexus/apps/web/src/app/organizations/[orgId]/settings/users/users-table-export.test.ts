import { describe, expect, it } from 'vitest';

import { usersToCsv, usersToXlsx } from './users-table-export';

describe('users table CSV export', () => {
  it('writes a header when there are no rows', () => {
    expect(usersToCsv([])).toBe('Name,Email,Role,Workspaces');
  });

  it('joins workspaces and quotes a field that contains a comma', () => {
    expect(
      usersToCsv([
        {
          name: 'Admin',
          email: 'admin@example.com',
          role: 'Owner',
          workspaces: 'ABI; Paris, France',
        },
      ])
    ).toBe(
      'Name,Email,Role,Workspaces\r\nAdmin,admin@example.com,Owner,"ABI; Paris, France"'
    );
  });

  it('escapes quotes inside a name', () => {
    const csv = usersToCsv([
      {
        name: 'Jean "JR" Ravenel',
        email: 'jr@example.com',
        role: 'Admin',
        workspaces: 'Core Team',
      },
    ]);
    expect(csv).toContain('"Jean ""JR"" Ravenel"');
  });
});

describe('users table XLSX export', () => {
  it('writes a zip Excel can open as .xlsx', () => {
    const bytes = usersToXlsx([
      {
        name: 'Admin',
        email: 'admin@example.com',
        role: 'Owner',
        workspaces: 'ABI; Core Team',
      },
    ]);
    const text = new TextDecoder().decode(bytes);
    expect(text.startsWith('PK')).toBe(true);
    expect(text).toContain('xl/worksheets/sheet1.xml');
    expect(text).toContain('Admin');
    expect(text).toContain('admin@example.com');
  });

  it('escapes XML in cell values', () => {
    const text = new TextDecoder().decode(
      usersToXlsx([
        {
          name: 'A <B> & C',
          email: 'a@example.com',
          role: 'Member',
          workspaces: '',
        },
      ])
    );
    expect(text).toContain('A &lt;B&gt; &amp; C');
  });
});
