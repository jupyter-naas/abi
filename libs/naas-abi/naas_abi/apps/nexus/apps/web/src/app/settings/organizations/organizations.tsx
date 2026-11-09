'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { SystemFrame, SystemRefresh } from '../system/system';
import {
  createOrganization,
  deleteOrganization,
  listOrganizations,
  renameOrganization,
  type Fetcher,
} from './organizations-api';
import {
  deleteConfirmed,
  slugFromName,
  sortOrganizations,
  type PlatformOrganization,
} from './organizations-model';
import './organizations.css';

type RowState =
  | { mode: 'idle' }
  | { mode: 'rename'; name: string }
  | { mode: 'delete'; typed: string };

function OrganizationRow({
  organization,
  fetcher,
  onChanged,
}: {
  organization: PlatformOrganization;
  fetcher?: Fetcher;
  onChanged: () => void;
}) {
  const [state, setState] = useState<RowState>({ mode: 'idle' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rename = async () => {
    if (state.mode !== 'rename' || !state.name.trim()) return;
    setBusy(true);
    const answer = await renameOrganization(organization.id, state.name.trim(), fetcher);
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setError(null);
    setState({ mode: 'idle' });
    onChanged();
  };

  const remove = async () => {
    if (state.mode !== 'delete' || !deleteConfirmed(organization, state.typed)) return;
    setBusy(true);
    const answer = await deleteOrganization(organization.id, fetcher);
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setError(null);
    setState({ mode: 'idle' });
    onChanged();
  };

  return (
    <li className="platform-orgs-row" data-org={organization.id}>
      <div className="platform-orgs-row-main">
        <div className="platform-orgs-row-text">
          <span className="platform-orgs-row-name">{organization.name}</span>
          <span className="platform-orgs-row-meta">
            {organization.slug} · {organization.id}
          </span>
        </div>
        <div className="platform-orgs-row-actions">
          <Link className="platform-orgs-link" href={`/organizations/${encodeURIComponent(organization.id)}/settings`}>
            Settings
          </Link>
          <button
            type="button"
            className="platform-orgs-button"
            data-action="rename"
            onClick={() => {
              setError(null);
              setState({ mode: 'rename', name: organization.name });
            }}
          >
            Rename
          </button>
          <button
            type="button"
            className="platform-orgs-button platform-orgs-button-danger"
            data-action="delete"
            onClick={() => {
              setError(null);
              setState({ mode: 'delete', typed: '' });
            }}
          >
            Delete
          </button>
        </div>
      </div>
      {state.mode === 'rename' && (
        <form
          className="platform-orgs-inline"
          onSubmit={(event) => {
            event.preventDefault();
            void rename();
          }}
        >
          <input
            className="platform-orgs-input"
            aria-label={`New name of ${organization.name}`}
            data-field="rename"
            value={state.name}
            onChange={(event) => setState({ mode: 'rename', name: event.target.value })}
          />
          <button type="submit" className="platform-orgs-button" data-action="save" disabled={busy || !state.name.trim()}>
            Save
          </button>
          <button type="button" className="platform-orgs-button" onClick={() => setState({ mode: 'idle' })}>
            Cancel
          </button>
        </form>
      )}
      {state.mode === 'delete' && (
        <form
          className="platform-orgs-inline"
          onSubmit={(event) => {
            event.preventDefault();
            void remove();
          }}
        >
          <span className="platform-orgs-confirm-text">
            Type <strong>{organization.name}</strong> to delete it. An organization is deleted once it has no
            workspace left.
          </span>
          <input
            className="platform-orgs-input"
            aria-label={`Type ${organization.name} to confirm`}
            data-field="confirm"
            value={state.typed}
            onChange={(event) => setState({ mode: 'delete', typed: event.target.value })}
          />
          <button
            type="submit"
            className="platform-orgs-button platform-orgs-button-danger"
            data-action="confirm-delete"
            disabled={busy || !deleteConfirmed(organization, state.typed)}
          >
            Delete organization
          </button>
          <button type="button" className="platform-orgs-button" onClick={() => setState({ mode: 'idle' })}>
            Cancel
          </button>
        </form>
      )}
      {error && (
        <p className="platform-orgs-error" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

/** Every organization the caller may list: create, rename, delete (once it has no workspace). */
export function PlatformOrganizations({ fetcher, nonce = 0 }: { fetcher?: Fetcher; nonce?: number }) {
  const [organizations, setOrganizations] = useState<PlatformOrganization[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugEdited, setSlugEdited] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [reloads, setReloads] = useState(0);

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    void listOrganizations(fetcher).then((answer) => {
      if (!live) return;
      if (answer.ok) {
        setOrganizations(sortOrganizations(answer.data ?? []));
        setLoadError(null);
      } else {
        setLoadError(answer.error);
      }
    });
    return () => {
      live = false;
    };
  }, [fetcher, nonce, reloads]);

  const create = async () => {
    if (!name.trim() || !slug.trim()) return;
    setCreating(true);
    const answer = await createOrganization(name.trim(), slug.trim(), fetcher);
    setCreating(false);
    if (!answer.ok) {
      setCreateError(answer.error);
      return;
    }
    setCreateError(null);
    setName('');
    setSlug('');
    setSlugEdited(false);
    reload();
  };

  return (
    <div className="platform-orgs">
      <form
        className="platform-orgs-create"
        onSubmit={(event) => {
          event.preventDefault();
          void create();
        }}
      >
        <label className="platform-orgs-field">
          <span>Name</span>
          <input
            className="platform-orgs-input"
            data-field="name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (!slugEdited) setSlug(slugFromName(event.target.value));
            }}
          />
        </label>
        <label className="platform-orgs-field">
          <span>Slug</span>
          <input
            className="platform-orgs-input"
            data-field="slug"
            value={slug}
            onChange={(event) => {
              setSlug(event.target.value);
              setSlugEdited(true);
            }}
          />
        </label>
        <button
          type="submit"
          className="platform-orgs-button platform-orgs-button-primary"
          data-action="create"
          disabled={creating || !name.trim() || !slug.trim()}
        >
          Create organization
        </button>
        {createError && (
          <p className="platform-orgs-error" role="alert">
            {createError}
          </p>
        )}
      </form>
      {loadError && (
        <p className="platform-orgs-error" role="alert">
          {loadError}
        </p>
      )}
      {organizations === null && !loadError && <p className="platform-orgs-empty">Loading…</p>}
      {organizations !== null && organizations.length === 0 && (
        <p className="platform-orgs-empty">No organization yet.</p>
      )}
      {organizations !== null && organizations.length > 0 && (
        <ul className="platform-orgs-list">
          {organizations.map((organization) => (
            <OrganizationRow
              key={organization.id}
              organization={organization}
              fetcher={fetcher}
              onChanged={reload}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PlatformOrganizationsPage() {
  const [nonce, setNonce] = useState(0);
  return (
    <SystemFrame
      title="Organizations"
      subtitle="Every organization of the platform: create one, rename it, delete it once it has no workspace left"
      actions={<SystemRefresh onClick={() => setNonce((n) => n + 1)} />}
    >
      <PlatformOrganizations nonce={nonce} />
    </SystemFrame>
  );
}
