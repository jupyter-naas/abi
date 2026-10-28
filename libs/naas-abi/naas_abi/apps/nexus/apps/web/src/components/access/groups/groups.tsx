'use client';

import { useCallback, useEffect, useState } from 'react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachmentView, GroupView, PrincipalView } from '@/lib/iam-admin/types';
import { NO_PROVIDERS, fetchInviteProviders, type InviteProviders } from '@/lib/invitations';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownedHere } from '../access-scope';
import { AttachForm } from '../attachments/attach-form';
import { scopeLabel } from '../attachments/attachments-model';
import { AttachmentTable } from '../attachments/attachments-table';
import './groups.css';

const message = (e: unknown) => (e instanceof IamAdminError ? e.message : String(e));

export const principalLabel = (p: PrincipalView) => p.display_name || p.email || p.name || p.id;

type Props = AccessViewProps & {
  /** The identity providers an IdP group can be mapped from (tests pass their own). */
  loadProviders?: () => Promise<InviteProviders>;
};

/**
 * The groups of the scope: those it owns, which its admins create, fill and delete, and
 * (at a workspace) its organization's the caller attaches to there. A group's page lists its
 * members, the policies it holds at this scope, and, where `access` offers IdP mappings (the
 * platform), the IdP group claims that put people in it.
 */
export function GroupsView({ api, can, scope, directory, nonce, loadProviders = fetchInviteProviders }: Props) {
  const [groups, setGroups] = useState<PrincipalView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [deleting, setDeleting] = useState<PrincipalView | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    try {
      const items = (await api.listGroups(scope.value ?? undefined)).items;
      setGroups(items);
      setError(null);
      // One read per group for the member count: groups are few.
      const details = await Promise.all(items.map((g) => api.getGroup(g.id).catch(() => null)));
      setCounts(Object.fromEntries(details.flatMap((d) => (d ? [[d.id, d.members.length]] : []))));
    } catch (e) {
      setError(message(e));
    }
  }, [api, scope]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const act = async (run: () => Promise<unknown>) => {
    try {
      await run();
      setError(null);
      await load();
    } catch (e) {
      setError(message(e));
    }
  };

  if (groups === null) {
    return error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>;
  }

  return (
    <div className="access-group">
      {error && <p className="access-source-note" role="alert">{error}</p>}
      {can('iam:CreateGroup') && (
        <form
          className="access-group-create"
          onSubmit={(e) => {
            e.preventDefault();
            const value = name.trim();
            if (!value) return;
            void act(async () => {
              await api.createGroup(scope.value ? { name: value, scope: scope.value } : { name: value });
              setName('');
            });
          }}
        >
          <input className="access-input access-input-grow" aria-label="Group name" placeholder="New group name" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" className="access-button access-button-primary" disabled={!name.trim()}>
            Create group
          </button>
        </form>
      )}
      <div className="access-group-layout">
        <div className="access-table-wrap">
          <table className="access-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Id</th>
                <th>Owner</th>
                <th className="access-num">Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id} className="access-table-row" data-group={group.id} aria-selected={selected === group.id}>
                  <td>
                    <button type="button" className="access-row-toggle" aria-expanded={selected === group.id} onClick={() => setSelected(selected === group.id ? null : group.id)}>
                      {group.name ?? group.id}
                    </button>
                  </td>
                  <td className="access-mono">{group.id}</td>
                  <td>{scopeLabel(group.owner_scope ?? PLATFORM)}</td>
                  <td className="access-num">{counts[group.id] ?? '–'}</td>
                  <td>
                    {can('iam:DeleteGroup') && ownedHere(scope, group.owner_scope) && (
                      <button type="button" className="access-button" aria-label={`Delete ${group.name ?? group.id}`} onClick={() => setDeleting(group)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {groups.length === 0 && (
                <tr>
                  <td colSpan={5} className="access-empty">No groups.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {selected && (
          <GroupDetail
            key={selected}
            api={api}
            can={can}
            scope={scope}
            directory={directory}
            groupId={selected}
            owned={ownedHere(scope, groups.find((g) => g.id === selected)?.owner_scope)}
            loadProviders={loadProviders}
            onChanged={load}
          />
        )}
      </div>
      {deleting && (
        <div className="access-group-confirm" role="dialog" aria-label="Delete group">
          <p>
            Delete <strong>{deleting.name ?? deleting.id}</strong>? Its members lose what it gave them.
          </p>
          <div className="access-group-actions">
            <button type="button" className="access-button" onClick={() => setDeleting(null)}>Cancel</button>
            <button
              type="button"
              className="access-button access-button-primary"
              onClick={() => {
                const target = deleting;
                setDeleting(null);
                if (selected === target.id) setSelected(null);
                void act(() => api.deleteGroup(target.id));
              }}
            >
              Delete group
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

type Candidate = { id: string; label: string };

function GroupDetail({
  api,
  can,
  scope,
  directory,
  groupId,
  owned,
  loadProviders,
  onChanged,
}: Omit<AccessViewProps, 'nonce'> & {
  groupId: string;
  /** Owned by this scope: its members change here. One owned above is only attached to. */
  owned: boolean;
  loadProviders: () => Promise<InviteProviders>;
  onChanged: () => Promise<void>;
}) {
  const [group, setGroup] = useState<GroupView | null>(null);
  const [held, setHeld] = useState<AttachmentView[] | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [providers, setProviders] = useState<InviteProviders>(NO_PROVIDERS);
  const [error, setError] = useState<string | null>(null);
  const [member, setMember] = useState('');
  const [provider, setProvider] = useState('');
  const [claim, setClaim] = useState('');
  const mapsIdp = can('iam:MapIdpGroup') || can('iam:UnmapIdpGroup');

  const loadHeld = useCallback(async () => {
    if (!can('iam:ListAttachments')) return;
    try {
      const found = await api.listAttachments({ principal_id: groupId, ...(scope.value ? { scope: scope.value } : {}) });
      setHeld(found.items);
    } catch (e) {
      setHeld([]);
      setError(message(e));
    }
  }, [api, can, groupId, scope]);

  useEffect(() => {
    let cancelled = false;
    api.getGroup(groupId).then((g) => !cancelled && setGroup(g)).catch((e) => !cancelled && setError(message(e)));
    void loadHeld();
    // Candidates for the member picker: the scope's people, or, at the platform, every user
    // and service account for whoever may list them. Anyone else types an id.
    const people: Promise<Candidate[]> = scope.value
      ? directory.members(scope).then((ms) => ms.map((m) => ({ id: m.userId, label: m.name || m.email || m.userId })))
      : can('iam:ListPrincipals')
        ? Promise.all([api.listPrincipals('user'), api.listPrincipals('service_account')]).then(([users, accounts]) =>
            [...users.items, ...accounts.items].map((p) => ({ id: p.id, label: principalLabel(p) })),
          )
        : Promise.resolve([]);
    people.then((found) => !cancelled && setCandidates(found)).catch(() => undefined);
    if (mapsIdp) {
      loadProviders()
        .then((found) => {
          if (cancelled) return;
          setProviders(found);
          setProvider((current) => current || found.providers[0]?.name || '');
        })
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
  }, [api, can, directory, scope, groupId, loadHeld, loadProviders, mapsIdp]);

  const run = async (call: () => Promise<GroupView>) => {
    try {
      setGroup(await call());
      setError(null);
      await onChanged();
    } catch (e) {
      setError(message(e));
    }
  };

  const detach = async (a: AttachmentView) => {
    try {
      await api.detach({ policy_id: a.policy_id, principal_id: a.principal_id, scope: a.scope });
      setError(null);
      await loadHeld();
    } catch (e) {
      setError(message(e));
    }
  };

  if (!group) return <div className="access-group-detail">{error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>}</div>;

  const inGroup = new Set(group.members.map((m) => m.id));
  const addable = candidates.filter((c) => !inGroup.has(c.id));

  return (
    <div className="access-group-detail" data-group-detail={group.id}>
      <h3 className="access-group-title">{group.name ?? group.id}</h3>
      {error && <p className="access-source-note" role="alert">{error}</p>}

      <section className="access-group-section">
        <h4 className="access-group-heading">Members</h4>
        <ul className="access-group-list">
          {group.members.map((m) => (
            <li key={m.id} className="access-group-item" data-member={m.id}>
              <span>
                {principalLabel(m)} <span className="access-mono">{m.kind === 'service_account' ? 'service account' : m.id}</span>
              </span>
              {owned && can('iam:RemoveGroupMember') && (
                <button type="button" className="access-button" aria-label={`Remove ${principalLabel(m)}`} onClick={() => void run(() => api.removeMember(group.id, m.id))}>
                  Remove
                </button>
              )}
            </li>
          ))}
          {group.members.length === 0 && <li className="access-empty">No members.</li>}
        </ul>
        {owned && can('iam:AddGroupMember') && (
          <form
            className="access-group-create"
            onSubmit={(e) => {
              e.preventDefault();
              const id = member.trim();
              if (!id) return;
              void run(() => api.addMember(group.id, id)).then(() => setMember(''));
            }}
          >
            <input className="access-input access-input-grow" aria-label="Member id" list={`members-${group.id}`} placeholder="Pick a person, or type an id" value={member} onChange={(e) => setMember(e.target.value)} />
            <datalist id={`members-${group.id}`}>
              {addable.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </datalist>
            <button type="submit" className="access-button access-button-primary" disabled={!member.trim()}>
              Add member
            </button>
          </form>
        )}
      </section>

      {held !== null && (
        <section className="access-group-section" aria-label="Policies of the group">
          <h4 className="access-group-heading">Policies {scope.value ? 'here' : ''}</h4>
          <AttachmentTable items={held} canDetach={can('iam:DetachPolicy')} onDetach={(a) => void detach(a)} showScope={!scope.value} />
          {can('iam:AttachPolicy') && (
            <AttachForm api={api} scope={scope.value} principals={[]} principalId={group.id} onAttached={() => void loadHeld()} />
          )}
        </section>
      )}

      {mapsIdp && (
        <section className="access-group-section">
          <h4 className="access-group-heading">IdP group claims</h4>
          <p className="access-group-hint">People whose identity provider sends one of these group claims join this group when they sign in.</p>
          <ul className="access-group-list">
            {group.idp_mappings.map((m) => (
              <li key={`${m.provider}/${m.claim_value}`} className="access-group-item" data-mapping={`${m.provider}/${m.claim_value}`}>
                <span>
                  <span className="access-mono">{m.claim_value}</span> from {m.provider}
                </span>
                {can('iam:UnmapIdpGroup') && (
                  <button type="button" className="access-button" aria-label={`Unmap ${m.claim_value}`} onClick={() => void run(() => api.unmapIdpGroup(group.id, m))}>
                    Remove
                  </button>
                )}
              </li>
            ))}
            {group.idp_mappings.length === 0 && <li className="access-empty">No mapping.</li>}
          </ul>
          {can('iam:MapIdpGroup') && (
            <form
              className="access-group-create"
              onSubmit={(e) => {
                e.preventDefault();
                const value = claim.trim();
                if (!value || !provider) return;
                void run(() => api.mapIdpGroup(group.id, { provider, claim_value: value })).then(() => setClaim(''));
              }}
            >
              <select className="access-input" aria-label="Identity provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
                {providers.providers.length === 0 && <option value="">No provider configured</option>}
                {providers.providers.map((p) => (
                  <option key={p.name} value={p.name}>{p.display_name || p.name}</option>
                ))}
              </select>
              <input className="access-input access-input-grow" aria-label="Group claim value" placeholder="Value of the group claim" value={claim} onChange={(e) => setClaim(e.target.value)} />
              <button type="submit" className="access-button access-button-primary" disabled={!claim.trim() || !provider}>
                Map group
              </button>
            </form>
          )}
        </section>
      )}
    </div>
  );
}
