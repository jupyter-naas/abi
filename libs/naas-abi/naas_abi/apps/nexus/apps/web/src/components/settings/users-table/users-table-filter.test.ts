import { describe, expect, it } from 'vitest';

import { rowMatchesColumnFilter } from './users-table-filter';

describe('users table column filter', () => {
  it('passes when the filter is empty', () => {
    expect(rowMatchesColumnFilter(['Admin'], undefined)).toBe(true);
    expect(rowMatchesColumnFilter(['Admin'], {})).toBe(true);
  });

  it('keeps rows whose cell is ticked', () => {
    expect(
      rowMatchesColumnFilter(['Admin', 'admin@example.com'], {
        selected: ['Admin'],
      })
    ).toBe(true);
    expect(
      rowMatchesColumnFilter(['Sylvain'], { selected: ['Admin'] })
    ).toBe(false);
  });

  it('matches a contains condition on any cell value', () => {
    expect(
      rowMatchesColumnFilter(['Valeo', 'Core Team'], {
        conditions: [{ operator: 'contains', value: 'vale' }],
      })
    ).toBe(true);
    expect(
      rowMatchesColumnFilter(['Core Team'], {
        conditions: [{ operator: 'contains', value: 'vale' }],
      })
    ).toBe(false);
  });
});
