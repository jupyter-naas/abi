'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  AlertCircle,
  Ban,
  ChevronDown,
  ChevronUp,
  Crown,
  Download,
  Filter,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  UserCircle,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { SearchBox } from '@/components/settings/search-box';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import {
  downloadTableExport,
  type UsersExportFormat,
} from '@/components/settings/users-table/users-table-export';
import { matchesSearch } from '../lib/search';
import { countFacets } from '../lib/page-helpers';
import {
  deactivateUser,
  deleteUser,
  deletionOf,
  inviteUser,
  listProviders,
  listUsers,
  reactivateUser,
  updateUser,
  type Fetcher,
} from './users-api';
import {
  cellValues,
  COLUMNS,
  count,
  createdDay,
  DEACTIVATED,
  deleteConfirmed,
  EXPORT_HEADERS,
  exportRow,
  inviteSummary,
  isSelf,
  NO_IAM_ID,
  NO_ORGANIZATION,
  personHref,
  searchTexts,
  sortUsers,
  statusLabel,
  USER_ACTIONS,
  type AdminUser,
  type ColumnId,
  type Deletion,
  type InvitationProvider,
  type SortDir,
} from './users-model';
import './users.css';

type Can = (action: string) => boolean;

type Panel =
  | { mode: 'none' }
  | { mode: 'rename'; name: string }
  | { mode: 'delete'; deletion: Deletion | null; loadError: string | null; typed: string };

function avatarUrl(avatar: string | null): string {
  if (!avatar) return '';
  return avatar.startsWith('/') ? `${getApiUrl()}${avatar}` : avatar;
}

/** What deleting takes away and what it leaves, from `GET /deletion`. */
function DeletionSummary({ deletion }: { deletion: Deletion }) {
  const { goes, stays } = deletion;
  const provider = goes.provider_account;
  return (
    <div className="platform-users-deletion" data-deletion="">
      <p className="platform-users-deletion-heading">Deleting {deletion.user.email} removes:</p>
      <ul data-list="goes">
        {provider &&
          (provider.managed_in_provider ? (
            <li>
              Nothing at {provider.display_name}: its people are managed there, so delete the account there
              too.
            </li>
          ) : (
            <li>Their account at the identity provider, {provider.display_name}.</li>
          ))}
        {goes.iam_user && (
          <li>
            Their IAM user, <code>{goes.iam_user}</code>, with {count(goes.attachments, 'policy attachment')}{' '}
            and their membership of {count(goes.groups, 'group')}.
          </li>
        )}
        {goes.memberships.length > 0 ? (
          <li>
            Their memberships:
            <ul>
              {goes.memberships.map((m) => (
                <li key={`${m.scope}:${m.role}`}>
                  {m.role} of {m.label}
                </li>
              ))}
            </ul>
          </li>
        ) : (
          <li>No organization or workspace membership.</li>
        )}
        <li>
          {count(goes.sessions, 'signed-in session')} and {count(goes.api_keys, 'API key')}.
        </li>
        {goes.invitations > 0 && <li>{count(goes.invitations, 'pending invitation')}.</li>}
      </ul>
      <p className="platform-users-deletion-heading">What stays:</p>
      {stays.workspaces.length > 0 ? (
        <ul data-list="stays">
          <li>
            What they wrote in these workspaces (conversations, files, graphs, agents...) stays there:
            <ul>
              {stays.workspaces.map((w) => (
                <li key={w.id}>{w.name || w.id}</li>
              ))}
            </ul>
          </li>
        </ul>
      ) : (
        <p data-list="stays">What they wrote anywhere stays: no workspace of theirs is deleted.</p>
      )}
    </div>
  );
}

function UserRow({
  user,
  can,
  self,
  fetcher,
  navigate,
  onChanged,
  onReplaced,
}: {
  user: AdminUser;
  can: Can;
  self: boolean;
  fetcher?: Fetcher;
  navigate: (href: string) => void;
  onChanged: () => void;
  onReplaced: (user: AdminUser) => void;
}) {
  const [panel, setPanel] = useState<Panel>({ mode: 'none' });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const href = personHref(user);

  const run = async (work: () => Promise<{ ok: true; data: AdminUser } | { ok: false; error: string }>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    const answer = await work();
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return false;
    }
    setNotice(answer.data.warning ?? null);
    onReplaced(answer.data);
    return true;
  };

  const rename = async () => {
    if (panel.mode !== 'rename' || !panel.name.trim()) return;
    const name = panel.name.trim();
    if (await run(() => updateUser(user.id, { name }, fetcher))) setPanel({ mode: 'none' });
  };

  const openDelete = async () => {
    setError(null);
    setNotice(null);
    setPanel({ mode: 'delete', deletion: null, loadError: null, typed: '' });
    const answer = await deletionOf(user.id, fetcher);
    setPanel((current) =>
      current.mode !== 'delete'
        ? current
        : answer.ok
          ? { ...current, deletion: answer.data }
          : { ...current, loadError: answer.error }
    );
  };

  const remove = async () => {
    if (panel.mode !== 'delete' || !panel.deletion || panel.deletion.blocked) return;
    if (!deleteConfirmed(user, panel.typed)) return;
    setBusy(true);
    setError(null);
    const answer = await deleteUser(user.id, panel.typed.trim(), fetcher);
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setPanel({ mode: 'none' });
    onChanged();
  };

  const actions = !self && (
    <span className="org-settings-users-row-actions platform-users-actions">
      {can(USER_ACTIONS.update) && (
        <button
          type="button"
          className="org-settings-users-edit"
          data-action="rename"
          title="Edit name"
          aria-label={`Edit the name of ${user.email}`}
          onClick={() => {
            setError(null);
            setPanel({ mode: 'rename', name: user.name });
          }}
        >
          <Pencil size={16} />
        </button>
      )}
      {can(USER_ACTIONS.update) && user.kind === 'account' && (
        <button
          type="button"
          className="org-settings-users-edit"
          data-action="superadmin"
          disabled={busy}
          title={user.is_superadmin ? 'Remove superadmin' : 'Make superadmin'}
          aria-label={`${user.is_superadmin ? 'Remove superadmin from' : 'Make superadmin'} ${user.email}`}
          onClick={() => void run(() => updateUser(user.id, { is_superadmin: !user.is_superadmin }, fetcher))}
        >
          <Crown size={16} />
        </button>
      )}
      {user.deactivated
        ? can(USER_ACTIONS.resume) && (
            <button
              type="button"
              className="org-settings-users-edit"
              data-action="reactivate"
              disabled={busy}
              title="Reactivate"
              aria-label={`Reactivate ${user.email}`}
              onClick={() => void run(() => reactivateUser(user.id, fetcher))}
            >
              <Play size={16} />
            </button>
          )
        : can(USER_ACTIONS.suspend) && (
            <button
              type="button"
              className="org-settings-users-edit"
              data-action="deactivate"
              disabled={busy}
              title="Deactivate: no sign-in, no API call; data and memberships kept"
              aria-label={`Deactivate ${user.email}`}
              onClick={() => void run(() => deactivateUser(user.id, fetcher))}
            >
              <Ban size={16} />
            </button>
          )}
      {can(USER_ACTIONS.remove) && (
        <button
          type="button"
          className="org-settings-users-remove"
          data-action="delete"
          title="Delete"
          aria-label={`Delete ${user.email}`}
          onClick={() => void openDelete()}
        >
          <Trash2 size={16} />
        </button>
      )}
    </span>
  );

  const organizations = cellValues(user, 'organizations');
  return (
    <>
      <tr
        data-user={user.id}
        className={href ? 'org-settings-users-row-link' : undefined}
        title={href ? 'Open their roles and permissions' : 'IAM has no user for them yet'}
        onClick={(event) => {
          if (!href) return;
          // The row's own buttons and forms keep their action.
          if ((event.target as HTMLElement).closest('button, a, input, select, label, form')) return;
          navigate(href);
        }}
      >
        <td>
          <div className="org-settings-users-row-start">
            {avatarUrl(user.avatar) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarUrl(user.avatar)} alt="" className="org-settings-users-avatar-image" />
            ) : (
              <div className="org-settings-users-avatar">{(user.name || user.email || '?').charAt(0).toUpperCase()}</div>
            )}
            <div className="org-settings-users-identity">
              <p className="org-settings-users-name">
                {user.name || user.email}
                {self && <span className="platform-users-badge">You</span>}
              </p>
              <p className="org-settings-users-email">{user.email}</p>
            </div>
          </div>
        </td>
        <td className="platform-users-mono">{user.principal_id ?? <span className="platform-users-muted">{NO_IAM_ID}</span>}</td>
        <td>
          <span className={`platform-users-status is-${user.status}`} data-field="status">
            {statusLabel(user)}
          </span>
          {user.deactivated && (
            <span className="platform-users-badge is-deactivated" data-field="deactivated">
              {DEACTIVATED}
            </span>
          )}
        </td>
        <td data-field="superadmin">
          {user.is_superadmin ? (
            <span className="platform-users-badge is-superadmin">
              <Crown size={12} /> Superadmin
            </span>
          ) : (
            <span className="platform-users-muted">No</span>
          )}
        </td>
        <td data-field="organizations">
          {user.organizations.length > 0 ? (
            organizations.join(', ')
          ) : (
            <span className="platform-users-muted">{NO_ORGANIZATION}</span>
          )}
        </td>
        <td>{createdDay(user)}</td>
        <td className="platform-users-actions-cell">{actions}</td>
      </tr>
      {(panel.mode !== 'none' || error || notice) && (
        <tr className="platform-users-panel-row" data-panel={user.id}>
          <td colSpan={COLUMNS.length + 1}>
            {panel.mode === 'rename' && (
              <form
                className="platform-users-inline"
                onSubmit={(event) => {
                  event.preventDefault();
                  void rename();
                }}
              >
                <input
                  className="platform-users-input"
                  data-field="rename"
                  aria-label={`New name of ${user.email}`}
                  value={panel.name}
                  onChange={(event) => setPanel({ mode: 'rename', name: event.target.value })}
                />
                <button type="submit" className="platform-users-button" data-action="save" disabled={busy || !panel.name.trim()}>
                  Save
                </button>
                <button type="button" className="platform-users-button" onClick={() => setPanel({ mode: 'none' })}>
                  Cancel
                </button>
              </form>
            )}
            {panel.mode === 'delete' && (
              <div className="platform-users-delete">
                {!panel.deletion && !panel.loadError && <p className="platform-users-muted">Reading what goes…</p>}
                {panel.loadError && (
                  <p className="platform-users-error" role="alert">
                    {panel.loadError}
                  </p>
                )}
                {panel.deletion && <DeletionSummary deletion={panel.deletion} />}
                {panel.deletion?.blocked && (
                  <p className="platform-users-error" role="alert" data-field="blocked">
                    {panel.deletion.blocked}
                  </p>
                )}
                <form
                  className="platform-users-inline"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void remove();
                  }}
                >
                  {panel.deletion && !panel.deletion.blocked && (
                    <>
                      <span className="platform-users-confirm-text">
                        Type <strong>{user.email}</strong> to delete the account.
                      </span>
                      <input
                        className="platform-users-input"
                        data-field="confirm"
                        aria-label={`Type ${user.email} to confirm`}
                        value={panel.typed}
                        onChange={(event) => setPanel({ ...panel, typed: event.target.value })}
                      />
                      <button
                        type="submit"
                        className="platform-users-button platform-users-button-danger"
                        data-action="confirm-delete"
                        disabled={busy || !deleteConfirmed(user, panel.typed)}
                      >
                        Delete account
                      </button>
                    </>
                  )}
                  <button type="button" className="platform-users-button" onClick={() => setPanel({ mode: 'none' })}>
                    Cancel
                  </button>
                </form>
              </div>
            )}
            {error && (
              <p className="platform-users-error" role="alert">
                {error}
              </p>
            )}
            {notice && (
              <p className="platform-users-notice" role="status">
                {notice}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function InviteForm({ fetcher, onInvited }: { fetcher?: Fetcher; onInvited: () => void }) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [providers, setProviders] = useState<InvitationProvider[]>([]);
  const [provider, setProvider] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [said, setSaid] = useState<string[]>([]);

  useEffect(() => {
    let live = true;
    void listProviders(fetcher).then((answer) => {
      if (!live || !answer.ok) return;
      setProviders(answer.data.providers ?? []);
      setProvider(answer.data.default_provider ?? answer.data.providers?.[0]?.name ?? '');
    });
    return () => {
      live = false;
    };
  }, [fetcher]);

  const send = async () => {
    if (!email.trim()) return;
    setBusy(true);
    setError(null);
    setSaid([]);
    const answer = await inviteUser(
      {
        email: email.trim(),
        ...(name.trim() ? { name: name.trim() } : {}),
        ...(providers.length > 1 && provider ? { provider } : {}),
      },
      fetcher
    );
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setSaid(inviteSummary(answer.data));
    setEmail('');
    setName('');
    onInvited();
  };

  const managed = providers.find((p) => p.name === provider)?.managed_in_provider;
  return (
    <form
      className="platform-users-invite"
      data-form="invite"
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <label className="platform-users-field">
        <span>Email</span>
        <input
          className="platform-users-input"
          type="email"
          data-field="invite-email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>
      <label className="platform-users-field">
        <span>Name (optional)</span>
        <input
          className="platform-users-input"
          data-field="invite-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      {providers.length > 1 && (
        <label className="platform-users-field">
          <span>Identity provider</span>
          <select
            className="platform-users-input"
            data-field="invite-provider"
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
          >
            {providers.map((p) => (
              <option key={p.name} value={p.name}>
                {p.display_name || p.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="submit"
        className="platform-users-button platform-users-button-primary"
        data-action="send-invite"
        disabled={busy || !email.trim()}
      >
        Send invitation
      </button>
      {managed && (
        <p className="platform-users-hint">
          This provider manages its people: the person signs in with the account they have there.
        </p>
      )}
      {error && (
        <p className="platform-users-error" role="alert">
          {error}
        </p>
      )}
      {said.length > 0 && (
        <ul className="platform-users-outcome" role="status" data-field="invite-outcome">
          {said.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </form>
  );
}

/**
 * Every account of the platform, and the people invited who have none yet: search,
 * column filters, sort, export, and the lifecycle (invite, edit the name, superadmin,
 * deactivate, reactivate, delete), each button shown for the access action IAM gives.
 * A row opens the person's page in Roles & permissions; access is never shown here.
 */
export function PlatformUsers({
  can,
  selfId,
  fetcher,
  nonce = 0,
  navigate,
}: {
  can: Can;
  selfId: string | null;
  fetcher?: Fetcher;
  nonce?: number;
  navigate: (href: string) => void;
}) {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);
  const [inviting, setInviting] = useState(false);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Partial<Record<ColumnId, ColumnFilterState>>>({});
  const [sortKey, setSortKey] = useState<ColumnId>('user');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [openFilter, setOpenFilter] = useState<{ id: ColumnId; left: number; top: number } | null>(null);

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    void listUsers(fetcher).then((answer) => {
      if (!live) return;
      if (answer.ok) {
        setUsers(answer.data ?? []);
        setLoadError(null);
      } else {
        setLoadError(answer.error);
      }
    });
    return () => {
      live = false;
    };
  }, [fetcher, nonce, reloads]);

  const replace = useCallback(
    (changed: AdminUser) => setUsers((current) => current?.map((u) => (u.id === changed.id ? changed : u)) ?? null),
    []
  );

  const all = useMemo(() => users ?? [], [users]);
  const visible = useMemo(
    () =>
      sortUsers(
        all.filter(
          (user) =>
            matchesSearch(searchTexts(user), search) &&
            COLUMNS.every((column) => rowMatchesColumnFilter(cellValues(user, column.id), filters[column.id]))
        ),
        sortKey,
        sortDir
      ),
    [all, search, filters, sortKey, sortDir]
  );

  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(all.flatMap((user) => cellValues(user, columnId as ColumnId))).filter((bucket) =>
        bucket.value.toLowerCase().includes(needle)
      );
    },
    [all]
  );

  const toggleSort = (column: ColumnId) => {
    if (sortKey === column) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(column);
    setSortDir('asc');
  };

  const exportVisible = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(EXPORT_HEADERS, visible.map(exportRow), format, `users_${date}`, 'Users');
  };

  const filtered = search.trim() !== '' || COLUMNS.some((column) => !isBlank(filters[column.id]));

  return (
    <div className="org-settings-users-page platform-users-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Users"
          badge={users ? count(users.length, 'user') : undefined}
          subtitle="Every account of the platform, and the people invited who have not signed in yet"
          actions={
            <>
              <button type="button" className="org-settings-users-secondary-button" onClick={reload} title="Refresh">
                <RefreshCw size={16} />
              </button>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="org-settings-users-secondary-button"
                    data-action="export"
                    disabled={visible.length === 0}
                  >
                    <Download size={16} />
                    Export
                    <ChevronDown size={14} />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content align="end" sideOffset={4} className="org-settings-users-export-menu">
                    <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => exportVisible('csv')}>
                      CSV
                    </DropdownMenu.Item>
                    <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => exportVisible('xlsx')}>
                      Excel (.xlsx)
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
              {can(USER_ACTIONS.invite) && (
                <button
                  type="button"
                  className="org-settings-primary-button"
                  data-action="invite"
                  aria-expanded={inviting}
                  onClick={() => setInviting((open) => !open)}
                >
                  <Plus size={16} />
                  Invite
                </button>
              )}
            </>
          }
        />

        {inviting && can(USER_ACTIONS.invite) && <InviteForm fetcher={fetcher} onInvited={reload} />}

        {loadError && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search name, email, IAM id, status, organization..."
          label="Search users"
        />

        {filtered && (
          <p className="org-settings-users-filter-meta">
            {visible.length} of {count(all.length, 'user')}
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setFilters({});
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap">
          {users === null && !loadError ? (
            <div className="org-settings-loading">Loading users...</div>
          ) : users !== null && users.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <UserCircle size={24} />
              </div>
              <p className="org-settings-empty-title">No users yet</p>
            </div>
          ) : users !== null ? (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {COLUMNS.map((column) => {
                    const sorted = sortKey === column.id;
                    const active = !isBlank(filters[column.id]);
                    return (
                      <th key={column.id}>
                        <div className="org-settings-users-th">
                          <button
                            type="button"
                            className="org-settings-users-sort"
                            data-sort={column.id}
                            onClick={() => toggleSort(column.id)}
                            title="Sort"
                          >
                            <span>{column.label}</span>
                            {sorted && sortDir === 'asc' && <ChevronUp size={12} />}
                            {sorted && sortDir === 'desc' && <ChevronDown size={12} />}
                          </button>
                          <button
                            type="button"
                            className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                            data-filter-trigger=""
                            title="Filter"
                            onClick={(event) => {
                              if (openFilter?.id === column.id) {
                                setOpenFilter(null);
                                return;
                              }
                              const rect = event.currentTarget.getBoundingClientRect();
                              setOpenFilter({ id: column.id, left: rect.left, top: rect.bottom + 4 });
                            }}
                          >
                            <Filter size={11} />
                          </button>
                        </div>
                        {openFilter?.id === column.id && (
                          <ColumnFilterPopover
                            columnId={column.id}
                            label={column.label}
                            datatype="string"
                            facetable
                            anchor={{ left: openFilter.left, top: openFilter.top }}
                            state={filters[column.id]}
                            onChange={(next) => setFilters((current) => ({ ...current, [column.id]: next }))}
                            onClear={() =>
                              setFilters((current) => {
                                const next = { ...current };
                                delete next[column.id];
                                return next;
                              })
                            }
                            loadFacets={loadFacets}
                            onClose={() => setOpenFilter(null)}
                          />
                        )}
                      </th>
                    );
                  })}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={COLUMNS.length + 1} className="org-settings-users-no-match">
                      No users match the current search and filters
                    </td>
                  </tr>
                )}
                {visible.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    can={can}
                    self={isSelf(user, selfId)}
                    fetcher={fetcher}
                    navigate={navigate}
                    onChanged={reload}
                    onReplaced={replace}
                  />
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        <p className="org-settings-footnote">
          A row opens the person&apos;s page in Roles &amp; permissions, where their roles, groups and policies
          are seen and attached: this page does not show or change access. Deactivating stops their sign-in at
          the identity provider and every API call, and keeps their data and memberships. Nobody deactivates,
          deletes or demotes themselves, and the platform always keeps one administrator.
        </p>
      </div>
    </div>
  );
}

export default function PlatformUsersPage() {
  const router = useRouter();
  const selfId = useAuthStore((s) => s.user?.id ?? null);
  const { actions } = usePlatformSettingsAccess();
  const can = useCallback((action: string) => actions?.[action] === true, [actions]);
  const navigate = useCallback((href: string) => router.push(href), [router]);
  return <PlatformUsers can={can} selfId={selfId} navigate={navigate} />;
}
