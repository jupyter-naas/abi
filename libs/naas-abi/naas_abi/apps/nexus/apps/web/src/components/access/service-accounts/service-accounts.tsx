'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { KeyRound, Pause, Play, Plus, Trash2 } from 'lucide-react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { KeyView, PolicyView, ServiceAccountView } from '@/lib/iam-admin/types';
import type { AccessViewProps, PlatformViewProps } from '../access-props';
import {
  AccessHeaderAction,
  ListHead,
  ListSearch,
  NameCell,
  RowActions,
  rowOpener,
  useAccessBadge,
  useListControls,
  type ListColumn,
} from '../access-list';
import { isServiceAccountPolicy } from '../builtins';
import { OneTimeSecretPanel, useOneTimeSecret } from './one-time-secret';
import './service-accounts.css';

const when = (value: string | null) => (value ? new Date(value).toLocaleDateString() : '–');
const message = (e: unknown) => (e instanceof IamAdminError ? e.message : String(e));

/** Service accounts (modules, scripts, CI) and their keys. A key's value appears once, when made. */
export function ServiceAccountsView({ api, can, nonce }: PlatformViewProps) {
  const [accounts, setAccounts] = useState<ServiceAccountView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [deleting, setDeleting] = useState<ServiceAccountView | null>(null);
  const [typed, setTyped] = useState('');
  const { secret, reveal, dismiss } = useOneTimeSecret();

  const load = useCallback(async () => {
    try {
      setAccounts((await api.listServiceAccounts()).items);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api]);

  // A refresh from the header also forgets a value nobody copied.
  useEffect(() => {
    dismiss();
    void load();
  }, [load, nonce, dismiss]);

  const act = async (run: () => Promise<unknown>) => {
    try {
      await run();
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  const openAccount = (id: string) => {
    dismiss();
    setOpen(open === id ? null : id);
  };

  const [creating, setCreating] = useState(false);
  const columns: ListColumn<ServiceAccountView>[] = [
    {
      id: 'name',
      label: 'Service account',
      sortBy: (a) => (a.name ?? a.id).toLowerCase(),
      values: (a) => [a.name ?? a.id],
    },
    { id: 'kind', label: 'Kind', sortBy: (a) => a.account_kind, values: (a) => [a.account_kind] },
    { id: 'status', label: 'Status', sortBy: (a) => a.status, values: (a) => [a.status] },
    { id: 'keys', label: 'Active keys', sortBy: (a) => a.active_keys, values: (a) => [String(a.active_keys)] },
  ];
  const list = useListControls(accounts, {
    searchText: (a) => [a.name, a.id, a.account_kind, a.status],
    columns,
    initialSort: 'name',
  });
  useAccessBadge(accounts?.length ?? null, 'service account');

  if (accounts === null) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  return (
    <div className="access-sa org-settings-users-main">
      {can('iam:CreateServiceAccount') && (
        <AccessHeaderAction>
          <button
            type="button"
            className="org-settings-primary-button"
            data-action="create-service-account"
            onClick={() => setCreating(true)}
          >
            <Plus size={16} />
            Create service account
          </button>
        </AccessHeaderAction>
      )}
      {error && (
        <div className="org-settings-users-alert" role="alert">
          <span>{error}</span>
        </div>
      )}
      {creating && (
        <form
          className="access-sa-create platform-users-inline"
          onSubmit={(e) => {
            e.preventDefault();
            const value = name.trim();
            if (!value) return;
            void act(async () => {
              await api.createServiceAccount(value);
              setName('');
              setCreating(false);
            });
          }}
        >
          <input
            className="platform-users-input access-input-grow"
            aria-label="Service account name"
            placeholder="Name of a new service account (a script, CI)"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
          />
          <button type="submit" className="platform-users-button platform-users-button-primary" disabled={!name.trim()}>
            Create
          </button>
          <button type="button" className="platform-users-button" onClick={() => setCreating(false)}>
            Cancel
          </button>
        </form>
      )}
      <ListSearch
        value={list.search}
        onChange={list.setSearch}
        placeholder="Search name, kind, status…"
        label="Search service accounts"
        shown={list.visible.length}
        total={accounts.length}
        noun="service account"
        filtered={list.filtered}
        onClear={list.clear}
      />
      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table" aria-label="Service accounts">
          <ListHead columns={columns} controls={list} />
          <tbody>
            {list.visible.map((account) => (
              <Fragment key={account.id}>
                <tr
                  data-service-account={account.name ?? account.id}
                  aria-expanded={open === account.id}
                  title="Show its keys"
                  {...rowOpener(() => openAccount(account.id))}
                >
                  <td>
                    <NameCell name={account.name ?? account.id} detail={account.name ? account.id : undefined} />
                  </td>
                  <td>{account.account_kind}</td>
                  <td>
                    <span
                      className={`platform-users-badge${account.status === 'suspended' ? ' is-deactivated' : ''}`}
                      data-field="status"
                    >
                      {account.status}
                    </span>
                  </td>
                  <td>{account.active_keys}</td>
                  <RowActions>
                      <button
                        type="button"
                        className="org-settings-users-edit"
                        data-action="keys"
                        title={open === account.id ? 'Hide keys' : 'Show keys'}
                        aria-label={`Keys of ${account.name ?? account.id}`}
                        aria-expanded={open === account.id}
                        onClick={() => openAccount(account.id)}
                      >
                        <KeyRound size={16} />
                      </button>
                      {account.status === 'active' && can('iam:SuspendPrincipal') && (
                        <button
                          type="button"
                          className="org-settings-users-edit"
                          title="Suspend"
                          aria-label={`Suspend ${account.name ?? account.id}`}
                          onClick={() => void act(() => api.suspend(account.id))}
                        >
                          <Pause size={16} />
                        </button>
                      )}
                      {account.status === 'suspended' && can('iam:ResumePrincipal') && (
                        <button
                          type="button"
                          className="org-settings-users-edit"
                          title="Resume"
                          aria-label={`Resume ${account.name ?? account.id}`}
                          onClick={() => void act(() => api.resume(account.id))}
                        >
                          <Play size={16} />
                        </button>
                      )}
                      {account.account_kind !== 'builtin' && can('iam:DeletePrincipal') && (
                        <button
                          type="button"
                          className="org-settings-users-remove"
                          title="Delete"
                          aria-label={`Delete ${account.name ?? account.id}`}
                          onClick={() => {
                            setDeleting(account);
                            setTyped('');
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                  </RowActions>
                </tr>
                {open === account.id && (
                  <tr className="access-table-detail">
                    <td colSpan={columns.length + 1}>
                      <KeysPane
                        key={account.id}
                        api={api}
                        can={can}
                        account={account}
                        secret={secret}
                        reveal={reveal}
                        dismiss={dismiss}
                        onChanged={load}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {accounts.length > 0 && list.visible.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="org-settings-users-no-match">
                  No service accounts match the current search and filters
                </td>
              </tr>
            )}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="org-settings-users-no-match">
                  No service accounts.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {deleting && (
        <div className="access-sa-confirm platform-users-deletion" role="dialog" aria-label="Delete service account">
          <p>
            Deleting <strong>{deleting.name ?? deleting.id}</strong> revokes its keys and detaches its policies.
            Type its name to confirm.
          </p>
          <input
            className="platform-users-input"
            aria-label="Type the name to confirm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
          <div className="access-sa-actions">
            <button type="button" className="platform-users-button" onClick={() => setDeleting(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="platform-users-button platform-users-button-danger"
              disabled={typed !== (deleting.name ?? deleting.id)}
              onClick={() => {
                const target = deleting;
                setDeleting(null);
                if (open === target.id) setOpen(null);
                void act(() => api.deleteServiceAccount(target.id));
              }}
            >
              Delete service account
            </button>
          </div>
        </div>
      )}
      <ServiceAccountPolicies api={api} can={can} nonce={nonce} />
    </div>
  );
}

/** How many pages of policies are read to find the service accounts'. */
const MAX_POLICY_PAGES = 10;

/**
 * The policies of the service accounts, read-only: IAM's own (Nexus API, Engine, Engine job,
 * Built-in IdP, Module bootstrap) and each module's approved manifest ("Module <m>"). They are
 * listed here only, never on Policies nor as a policy to attach to a person or a group.
 */
export function ServiceAccountPolicies({ api, can, nonce }: PlatformViewProps) {
  const [policies, setPolicies] = useState<PolicyView[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const lists = can('iam:ListPolicies');

  useEffect(() => {
    if (!lists) return;
    let cancelled = false;
    (async () => {
      const found: PolicyView[] = [];
      let after: string | undefined;
      for (let page = 0; page < MAX_POLICY_PAGES; page += 1) {
        const read = await api.listPolicies(after);
        found.push(...read.items.filter((p) => isServiceAccountPolicy(p.id)));
        if (!read.next_after) break;
        after = read.next_after;
      }
      return found.sort((a, b) => a.name.localeCompare(b.name));
    })().then(
      (found) => !cancelled && setPolicies(found),
      () => !cancelled && setPolicies([]),
    );
    return () => {
      cancelled = true;
    };
  }, [api, lists, nonce]);

  if (!lists || !policies || policies.length === 0) return null;
  return (
    <section className="access-sa-policies" aria-label="Service-account policies" data-service-account-policies="">
      <h3 className="access-sa-policies-title">Service-account policies</h3>
      <p className="access-empty">
        What IAM&apos;s own accounts and each module act with. Managed by IAM and the module approvals: read-only,
        and shown nowhere else.
      </p>
      <table className="org-settings-users-table" aria-label="Service-account policies">
        <thead>
          <tr>
            <th>Policy</th>
            <th>Statements</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((policy) => (
            <Fragment key={policy.id}>
              <tr data-sa-policy={policy.id} {...rowOpener(() => setOpen(open === policy.id ? null : policy.id))}>
                <td>
                  <NameCell name={policy.name} detail={policy.id} />
                </td>
                <td>{policy.document.statements.length}</td>
              </tr>
              {open === policy.id && (
                <tr data-sa-policy-document={policy.id}>
                  <td colSpan={2}>
                    {policy.description && <p className="access-empty">{policy.description}</p>}
                    <pre className="access-sa-policy-document">{JSON.stringify(policy.document, null, 2)}</pre>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function KeysPane({
  api,
  can,
  account,
  secret,
  reveal,
  dismiss,
  onChanged,
}: Pick<AccessViewProps, 'api' | 'can'> & {
  account: ServiceAccountView;
  secret: ReturnType<typeof useOneTimeSecret>['secret'];
  reveal: ReturnType<typeof useOneTimeSecret>['reveal'];
  dismiss: () => void;
  onChanged: () => Promise<void>;
}) {
  const [keys, setKeys] = useState<KeyView[] | null>(null);
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setKeys((await api.listKeys(account.id)).items);
      setError(null);
    } catch (e) {
      setError(message(e));
    }
  }, [api, account.id]);

  useEffect(() => {
    void load();
    // Leaving this account forgets a value nobody copied.
    return () => dismiss();
  }, [load, dismiss]);

  const label = account.name ?? account.id;
  const run = async (call: () => Promise<{ key: KeyView; value: string } | unknown>, title?: string) => {
    try {
      const result = await call();
      if (title && result && typeof result === 'object' && 'value' in result) {
        reveal(title, (result as { value: string }).value);
      }
      setError(null);
      await load();
      await onChanged();
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <div className="access-sa-keys" data-keys-of={label}>
      {error && <p className="access-source-note" role="alert">{error}</p>}
      {secret && <OneTimeSecretPanel secret={secret} onClose={dismiss} />}
      {can('iam:CreateKey') && account.status === 'active' && (
        <form
          className="access-sa-create"
          onSubmit={(e) => {
            e.preventDefault();
            void run(
              () => api.createKey(account.id, { description: description.trim() }),
              `New key for ${label}`,
            ).then(() => setDescription(''));
          }}
        >
          <input
            className="access-input access-input-grow"
            aria-label="Key description"
            placeholder="What the key is for (prod, ci)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button type="submit" className="access-button access-button-primary">
            Create key
          </button>
        </form>
      )}
      <table className="access-table access-table-nested">
        <thead>
          <tr>
            <th>Key</th>
            <th>Description</th>
            <th>Created</th>
            <th>Expires</th>
            <th>Last used</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {(keys ?? []).map((key) => (
            <tr key={key.id} className="access-table-row" data-key-id={key.id}>
              <td className="access-mono">{key.prefix}</td>
              <td>{key.description || '–'}</td>
              <td>{when(key.created_at)}</td>
              <td>{when(key.expires_at)}</td>
              <td>{when(key.last_used_at)}</td>
              <td>{key.status}</td>
              <td className="access-sa-row-actions">
                {key.status === 'active' && can('iam:CreateKey') && can('iam:RevokeKey') && (
                  <button
                    type="button"
                    className="access-button"
                    aria-label={`Rotate ${key.prefix}`}
                    onClick={() => void run(() => api.rotateKey(account.id, key.id), `Rotated key for ${label}`)}
                  >
                    Rotate
                  </button>
                )}
                {key.status === 'active' && can('iam:RevokeKey') && (
                  <button
                    type="button"
                    className="access-button"
                    aria-label={`Revoke ${key.prefix}`}
                    onClick={() => void run(() => api.revokeKey(account.id, key.id))}
                  >
                    Revoke
                  </button>
                )}
              </td>
            </tr>
          ))}
          {keys !== null && keys.length === 0 && (
            <tr>
              <td colSpan={7} className="access-empty">No keys.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
