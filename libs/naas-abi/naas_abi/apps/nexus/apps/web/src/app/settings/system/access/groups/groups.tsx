'use client';

import { useCallback, useEffect, useState } from 'react';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { GroupView, PrincipalView } from '@/lib/iam-admin/types';
import { NO_PROVIDERS, fetchInviteProviders, type InviteProviders } from '@/lib/invitations';
import type { AccessViewProps } from '../access-props';
import './groups.css';

const message = (e: unknown) => (e instanceof IamAdminError ? e.message : String(e));

export const principalLabel = (p: PrincipalView) => p.display_name || p.email || p.name || p.id;

type Props = AccessViewProps & {
  /** The identity providers an IdP group can be mapped from (tests pass their own). */
  loadProviders?: () => Promise<InviteProviders>;
};

/** Groups: who is in them, and which IdP group claims put people there. */
export function GroupsView({ api, can, nonce, loadProviders = fetchInviteProviders }: Props) {
  const [groups, setGroups] = useState<PrincipalView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [org, setOrg] = useState('');
  const [deleting, setDeleting] = useState<PrincipalView | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const load = useCallback(async () => {
    try {
      const items = (await api.listGroups()).items;
      setGroups(items);
      setError(null);
      // One read per group for the member count: groups are few.
      const details = await Promise.all(items.map((g) => api.getGroup(g.id).catch(() => null)));
      setCounts(Object.fromEntries(details.flatMap((d) => (d ? [[d.id, d.members.length]] : []))));
    } catch (e) {
      setError(message(e));
    }
  }, [api]);

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
    return error ? <p className="system-source-note" role="alert">{error}</p> : <p className="system-empty">Loading…</p>;
  }

  return (
    <div className="access-group">
      {error && <p className="system-source-note" role="alert">{error}</p>}
      {can('iam:CreateGroup') && (
        <form
          className="access-group-create"
          onSubmit={(e) => {
            e.preventDefault();
            const value = name.trim();
            if (!value) return;
            void act(async () => {
              await api.createGroup({ name: value, org: org.trim() || null });
              setName('');
              setOrg('');
            });
          }}
        >
          <input className="system-input system-input-grow" aria-label="Group name" placeholder="New group name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="system-input" aria-label="Organization (optional)" placeholder="Organization (optional)" value={org} onChange={(e) => setOrg(e.target.value)} />
          <button type="submit" className="system-button system-button-primary" disabled={!name.trim()}>
            Create group
          </button>
        </form>
      )}
      <div className="access-group-layout">
        <div className="system-table-wrap">
          <table className="system-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Id</th>
                <th>Organization</th>
                <th className="system-num">Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id} className="system-table-row" data-group={group.id} aria-selected={selected === group.id}>
                  <td>
                    <button type="button" className="system-row-toggle" aria-expanded={selected === group.id} onClick={() => setSelected(selected === group.id ? null : group.id)}>
                      {group.name ?? group.id}
                    </button>
                  </td>
                  <td className="system-mono">{group.id}</td>
                  <td>{group.org ?? 'platform'}</td>
                  <td className="system-num">{counts[group.id] ?? '–'}</td>
                  <td>
                    {can('iam:DeleteGroup') && (
                      <button type="button" className="system-button" aria-label={`Delete ${group.name ?? group.id}`} onClick={() => setDeleting(group)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {groups.length === 0 && (
                <tr>
                  <td colSpan={5} className="system-empty">No groups.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {selected && (
          <GroupDetail key={selected} api={api} can={can} groupId={selected} loadProviders={loadProviders} onChanged={load} />
        )}
      </div>
      {deleting && (
        <div className="access-group-confirm" role="dialog" aria-label="Delete group">
          <p>
            Delete <strong>{deleting.name ?? deleting.id}</strong>? Its members lose what it gave them.
          </p>
          <div className="access-group-actions">
            <button type="button" className="system-button" onClick={() => setDeleting(null)}>Cancel</button>
            <button
              type="button"
              className="system-button system-button-primary"
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

function GroupDetail({
  api,
  can,
  groupId,
  loadProviders,
  onChanged,
}: Pick<AccessViewProps, 'api' | 'can'> & {
  groupId: string;
  loadProviders: () => Promise<InviteProviders>;
  onChanged: () => Promise<void>;
}) {
  const [group, setGroup] = useState<GroupView | null>(null);
  const [candidates, setCandidates] = useState<PrincipalView[]>([]);
  const [providers, setProviders] = useState<InviteProviders>(NO_PROVIDERS);
  const [error, setError] = useState<string | null>(null);
  const [member, setMember] = useState('');
  const [provider, setProvider] = useState('');
  const [claim, setClaim] = useState('');

  useEffect(() => {
    let cancelled = false;
    api.getGroup(groupId).then((g) => !cancelled && setGroup(g)).catch((e) => !cancelled && setError(message(e)));
    // Candidates for the member picker; a caller who cannot list them types an id instead.
    Promise.all([api.listPrincipals('user'), api.listPrincipals('service_account')])
      .then(([users, accounts]) => !cancelled && setCandidates([...users.items, ...accounts.items]))
      .catch(() => undefined);
    loadProviders()
      .then((found) => {
        if (cancelled) return;
        setProviders(found);
        setProvider((current) => current || found.providers[0]?.name || '');
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [api, groupId, loadProviders]);

  const run = async (call: () => Promise<GroupView>) => {
    try {
      setGroup(await call());
      setError(null);
      await onChanged();
    } catch (e) {
      setError(message(e));
    }
  };

  if (!group) return <div className="access-group-detail">{error ? <p className="system-source-note" role="alert">{error}</p> : <p className="system-empty">Loading…</p>}</div>;

  const inGroup = new Set(group.members.map((m) => m.id));
  const addable = candidates.filter((c) => !inGroup.has(c.id));

  return (
    <div className="access-group-detail" data-group-detail={group.id}>
      <h3 className="access-group-title">{group.name ?? group.id}</h3>
      {error && <p className="system-source-note" role="alert">{error}</p>}

      <section className="access-group-section">
        <h4 className="access-group-heading">Members</h4>
        <ul className="access-group-list">
          {group.members.map((m) => (
            <li key={m.id} className="access-group-item" data-member={m.id}>
              <span>
                {principalLabel(m)} <span className="system-mono">{m.kind === 'service_account' ? 'service account' : m.id}</span>
              </span>
              {can('iam:RemoveGroupMember') && (
                <button type="button" className="system-button" aria-label={`Remove ${principalLabel(m)}`} onClick={() => void run(() => api.removeMember(group.id, m.id))}>
                  Remove
                </button>
              )}
            </li>
          ))}
          {group.members.length === 0 && <li className="system-empty">No members.</li>}
        </ul>
        {can('iam:AddGroupMember') && (
          <form
            className="access-group-create"
            onSubmit={(e) => {
              e.preventDefault();
              const id = member.trim();
              if (!id) return;
              void run(() => api.addMember(group.id, id)).then(() => setMember(''));
            }}
          >
            <input className="system-input system-input-grow" aria-label="Member id" list={`members-${group.id}`} placeholder="Pick a user or service account, or type an id" value={member} onChange={(e) => setMember(e.target.value)} />
            <datalist id={`members-${group.id}`}>
              {addable.map((c) => (
                <option key={c.id} value={c.id}>{principalLabel(c)}</option>
              ))}
            </datalist>
            <button type="submit" className="system-button system-button-primary" disabled={!member.trim()}>
              Add member
            </button>
          </form>
        )}
      </section>

      <section className="access-group-section">
        <h4 className="access-group-heading">IdP group claims</h4>
        <p className="access-group-hint">People whose identity provider sends one of these group claims join this group when they sign in.</p>
        <ul className="access-group-list">
          {group.idp_mappings.map((m) => (
            <li key={`${m.provider}/${m.claim_value}`} className="access-group-item" data-mapping={`${m.provider}/${m.claim_value}`}>
              <span>
                <span className="system-mono">{m.claim_value}</span> from {m.provider}
              </span>
              {can('iam:UnmapIdpGroup') && (
                <button type="button" className="system-button" aria-label={`Unmap ${m.claim_value}`} onClick={() => void run(() => api.unmapIdpGroup(group.id, m))}>
                  Remove
                </button>
              )}
            </li>
          ))}
          {group.idp_mappings.length === 0 && <li className="system-empty">No mapping.</li>}
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
            <select className="system-input" aria-label="Identity provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providers.providers.length === 0 && <option value="">No provider configured</option>}
              {providers.providers.map((p) => (
                <option key={p.name} value={p.name}>{p.display_name || p.name}</option>
              ))}
            </select>
            <input className="system-input system-input-grow" aria-label="Group claim value" placeholder="Value of the group claim" value={claim} onChange={(e) => setClaim(e.target.value)} />
            <button type="submit" className="system-button system-button-primary" disabled={!claim.trim() || !provider}>
              Map group
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
