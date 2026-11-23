// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearViewFlag, setViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import { useTablesView } from './tables-view';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });
const signIn = (id: string) => useAuthStore.setState({ user: person(id), csrfToken: `csrf-${id}`, isAuthenticated: true });

function leaveTablesAsSeen() {
  const view = useTablesView.getState();
  view.setSearch('users');
  view.setSort('rows', 'desc');
  view.setOpenTable('users');
  view.rememberLabels([{ name: 'users', label: 'Users' }]);
}

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  signIn('one');
});

describe('Nexus tables, as they were left', () => {
  it('are kept for the same session', () => {
    leaveTablesAsSeen();
    expect(useTablesView.getState()).toMatchObject({ search: 'users', sortKey: 'rows', openTable: 'users' });
  });

  it('are forgotten when another account signs in', () => {
    leaveTablesAsSeen();
    signIn('two');
    expect(useTablesView.getState()).toMatchObject({
      search: '',
      columnFilters: {},
      sortKey: null,
      sortDir: 'asc',
      openTable: null,
      labels: {},
    });
  });

  it('are forgotten when a view (View as) starts', () => {
    leaveTablesAsSeen();
    setViewFlag({ workspaceId: 'ws-1', returnTo: null }, Date.now() + 60_000);
    expect(useTablesView.getState().search).toBe('');
    clearViewFlag();
  });
});
