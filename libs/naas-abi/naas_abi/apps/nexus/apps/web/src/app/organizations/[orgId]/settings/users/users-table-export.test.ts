import { describe, expect, it } from 'vitest';

import {
  columnLetter,
  tableToCsv,
  tableToXlsx,
  workbookToXlsx,
  usersToCsv,
  usersToXlsx,
} from './users-table-export';

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
          groups: 'ABI; Paris, France',
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
        groups: 'Core Team',
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
        groups: 'ABI; Core Team',
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
          groups: '',
        },
      ])
    );
    expect(text).toContain('A &lt;B&gt; &amp; C');
  });
});

describe('users export groups column', () => {
  it('names the groups column', () => {
    const csv = usersToCsv(
      [{ name: 'Ada', email: 'ada@example.com', role: 'Superadmin', groups: 'Acme; Beta' }],
      'Organizations'
    );
    expect(csv).toBe('Name,Email,Role,Organizations\r\nAda,ada@example.com,Superadmin,Acme; Beta');
    expect(new TextDecoder().decode(usersToXlsx([], 'Organizations'))).toContain('Organizations');
  });
});

describe('generic table export', () => {
  it('names spreadsheet columns past Z', () => {
    expect([0, 25, 26, 27, 51, 52].map(columnLetter)).toEqual(['A', 'Z', 'AA', 'AB', 'AZ', 'BA']);
  });

  it('writes every column as CSV', () => {
    expect(tableToCsv(['id', 'note'], [['1', 'a, b']])).toBe('id,note\r\n1,"a, b"');
  });

  it('writes cells past column Z and names the sheet after the table', () => {
    const headers = Array.from({ length: 27 }, (_, i) => `c${i}`);
    const xml = new TextDecoder().decode(tableToXlsx(headers, [], 'organizations'));
    expect(xml).toContain('r="AA1"');
    expect(xml).toContain('<sheet name="organizations"');
  });
});

describe('workbook export', () => {
  it('writes one sheet per table', () => {
    const xml = new TextDecoder().decode(
      workbookToXlsx([
        { name: 'users', headers: ['id'], rows: [['u-1']] },
        { name: 'workspace_resource_policies', headers: ['workspace_id'], rows: [] },
      ])
    );
    expect(xml).toContain('<sheet name="users" sheetId="1" r:id="rId1"/>');
    expect(xml).toContain('<sheet name="workspace_resource_policies" sheetId="2" r:id="rId2"/>');
    expect(xml).toContain('xl/worksheets/sheet2.xml');
    expect(xml).toContain('Target="worksheets/sheet2.xml"');
  });

  it('cuts sheet names to 31 characters', () => {
    const xml = new TextDecoder().decode(
      workbookToXlsx([{ name: 'x'.repeat(40), headers: ['a'], rows: [] }])
    );
    expect(xml).toContain(`<sheet name="${'x'.repeat(31)}"`);
  });
});
