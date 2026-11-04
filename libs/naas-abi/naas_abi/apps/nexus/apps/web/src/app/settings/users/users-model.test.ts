import { describe, expect, it } from 'vitest';
import {
  cellValues,
  deleteConfirmed,
  errorText,
  EXPORT_HEADERS,
  exportRow,
  inviteSummary,
  isSelf,
  personHref,
  searchTexts,
  sortUsers,
  type AdminUser,
} from './users-model';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';

const user = (over: Partial<AdminUser> = {}): AdminUser => ({
  id: 'usr_a',
  kind: 'account',
  email: 'alice@example.com',
  name: 'Alice',
  avatar: null,
  principal_id: 'usr_a',
  status: 'signed_in',
  deactivated: false,
  is_superadmin: false,
  created_at: '2026-10-01T09:30:00',
  organizations: [],
  provider: 'builtin',
  ...over,
});

describe('cells', () => {
  it('say the status, deactivated or not, as the filter sees it', () => {
    expect(cellValues(user(), 'status')).toEqual(['Signed in', 'Active']);
    expect(cellValues(user({ status: 'invited', deactivated: true }), 'status')).toEqual([
      'Invited, not yet',
      'Deactivated',
    ]);
    expect(rowMatchesColumnFilter(cellValues(user({ deactivated: true }), 'status'), { selected: ['Deactivated'] })).toBe(
      true
    );
    expect(rowMatchesColumnFilter(cellValues(user(), 'status'), { selected: ['Deactivated'] })).toBe(false);
  });

  it('name each organization once, sorted, or none', () => {
    expect(cellValues(user(), 'organizations')).toEqual(['No organization']);
    expect(
      cellValues(
        user({
          organizations: [
            { id: 'o2', name: 'Zeta', role: 'member' },
            { id: 'o1', name: 'Acme', role: 'owner' },
          ],
        }),
        'organizations'
      )
    ).toEqual(['Acme', 'Zeta']);
  });

  it('say superadmin, the IAM id or that there is none, and the day created', () => {
    expect(cellValues(user({ is_superadmin: true }), 'superadmin')).toEqual(['Superadmin']);
    expect(cellValues(user({ principal_id: null }), 'iam')).toEqual(['None yet']);
    expect(cellValues(user(), 'created')).toEqual([new Date('2026-10-01T09:30:00').toISOString().slice(0, 10)]);
  });

  it('are what the search looks in, with the provider and the roles', () => {
    expect(searchTexts(user({ organizations: [{ id: 'o', name: 'Acme', role: 'admin' }] }))).toEqual(
      expect.arrayContaining(['Alice', 'alice@example.com', 'usr_a', 'Acme', 'admin', 'builtin'])
    );
  });
});

describe('sortUsers', () => {
  it('sorts by a column, both ways, then by email', () => {
    const rows = [user({ id: 'b', name: 'Bob', email: 'b@x' }), user({ id: 'a', name: 'alice', email: 'a@x' })];
    expect(sortUsers(rows, 'user', 'asc').map((u) => u.id)).toEqual(['a', 'b']);
    expect(sortUsers(rows, 'user', 'desc').map((u) => u.id)).toEqual(['b', 'a']);
    const same = [user({ id: 'z', email: 'z@x' }), user({ id: 'y', email: 'y@x' })];
    expect(sortUsers(same, 'status', 'asc').map((u) => u.id)).toEqual(['y', 'z']);
  });
});

describe('export', () => {
  it('has every column, the organizations with their role', () => {
    expect(EXPORT_HEADERS).toHaveLength(exportRow(user()).length);
    expect(
      exportRow(
        user({ is_superadmin: true, deactivated: true, organizations: [{ id: 'o', name: 'Acme', role: 'owner' }] })
      )
    ).toEqual(['Alice', 'alice@example.com', 'usr_a', 'Signed in', 'yes', 'yes', 'Acme (owner)', expect.any(String), 'builtin']);
  });
});

describe('the person, oneself and the delete confirmation', () => {
  it('opens the person page on the IAM id, nothing without one', () => {
    expect(personHref(user({ principal_id: 'usr_x/y' }))).toBe('/settings/roles?section=people&person=usr_x%2Fy');
    expect(personHref(user({ principal_id: null }))).toBeNull();
  });

  it('knows oneself by the Nexus id or the IAM id', () => {
    expect(isSelf(user({ id: 'old-1', principal_id: 'usr_a' }), 'old-1')).toBe(true);
    expect(isSelf(user({ id: 'old-1', principal_id: 'usr_a' }), 'usr_a')).toBe(true);
    expect(isSelf(user(), 'usr_b')).toBe(false);
    expect(isSelf(user(), null)).toBe(false);
  });

  it('deletes once the email is typed back', () => {
    expect(deleteConfirmed(user(), 'alice')).toBe(false);
    expect(deleteConfirmed(user(), ' Alice@Example.com ')).toBe(true);
    expect(deleteConfirmed(user({ email: '' }), '')).toBe(false);
  });
});

describe('words', () => {
  it('give the API detail, else the status', () => {
    expect(errorText(400, { detail: 'You cannot deactivate yourself' })).toBe('You cannot deactivate yourself');
    expect(errorText(422, { detail: [{ msg: 'bad email' }] })).toBe('bad email');
    expect(errorText(404, null)).toBe('User not found.');
    expect(errorText(500, null)).toBe('The API answered 500.');
  });

  it('say what an invitation did', () => {
    const said = inviteSummary({
      user: user({ email: 'new@example.com', status: 'invited' }),
      user_created: true,
      sign_in_email_sent: false,
      provisioning_skipped: false,
      renewed: false,
      warning: 'The provider could not mail them',
    });
    expect(said).toEqual([
      'new@example.com invited.',
      'Their account was made at the identity provider.',
      'No email could be sent: send them the sign-in link yourself.',
      'The provider could not mail them',
    ]);
  });
});
