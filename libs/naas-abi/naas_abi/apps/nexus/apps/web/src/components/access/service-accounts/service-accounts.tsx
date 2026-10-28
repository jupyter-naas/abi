'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { KeyView, ServiceAccountView } from '@/lib/iam-admin/types';
import type { AccessViewProps, PlatformViewProps } from '../access-props';
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

  if (accounts === null) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  return (
    <div className="access-sa">
      {error && <p className="access-source-note" role="alert">{error}</p>}
      {can('iam:CreateServiceAccount') && (
        <form
          className="access-sa-create"
          onSubmit={(e) => {
            e.preventDefault();
            const value = name.trim();
            if (!value) return;
            void act(async () => {
              await api.createServiceAccount(value);
              setName('');
            });
          }}
        >
          <input
            className="access-input access-input-grow"
            aria-label="Service account name"
            placeholder="Name of a new service account (a script, CI)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button type="submit" className="access-button access-button-primary" disabled={!name.trim()}>
            Create
          </button>
        </form>
      )}
      <div className="access-table-wrap">
        <table className="access-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Status</th>
              <th className="access-num">Active keys</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <Fragment key={account.id}>
                <tr className="access-table-row" data-service-account={account.name ?? account.id}>
                  <td>
                    <button type="button" className="access-row-toggle" aria-expanded={open === account.id} onClick={() => openAccount(account.id)}>
                      <span className="access-mono">{account.name ?? account.id}</span>
                    </button>
                  </td>
                  <td>{account.account_kind}</td>
                  <td>{account.status}</td>
                  <td className="access-num">{account.active_keys}</td>
                  <td className="access-sa-row-actions">
                    {account.status === 'active' && can('iam:SuspendPrincipal') && (
                      <button type="button" className="access-button" onClick={() => void act(() => api.suspend(account.id))}>
                        Suspend
                      </button>
                    )}
                    {account.status === 'suspended' && can('iam:ResumePrincipal') && (
                      <button type="button" className="access-button" onClick={() => void act(() => api.resume(account.id))}>
                        Resume
                      </button>
                    )}
                    {account.account_kind !== 'builtin' && can('iam:DeletePrincipal') && (
                      <button
                        type="button"
                        className="access-button"
                        aria-label={`Delete ${account.name ?? account.id}`}
                        onClick={() => {
                          setDeleting(account);
                          setTyped('');
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
                {open === account.id && (
                  <tr className="access-table-detail">
                    <td colSpan={5}>
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
            {accounts.length === 0 && (
              <tr>
                <td colSpan={5} className="access-empty">No service accounts.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {deleting && (
        <div className="access-sa-confirm" role="dialog" aria-label="Delete service account">
          <p>
            Deleting <strong>{deleting.name ?? deleting.id}</strong> revokes its keys and detaches its policies.
            Type its name to confirm.
          </p>
          <input
            className="access-input"
            aria-label="Type the name to confirm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
          />
          <div className="access-sa-actions">
            <button type="button" className="access-button" onClick={() => setDeleting(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="access-button access-button-primary"
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
    </div>
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
