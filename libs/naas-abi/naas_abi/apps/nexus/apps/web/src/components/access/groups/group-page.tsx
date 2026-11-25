'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { SettingsSection } from '@/components/settings/settings-ui';
import { RolePickerDialog } from '@/components/people/role-picker-dialog';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { AttachablePolicy, AttachmentView, GroupView, PrincipalKind, PrincipalView } from '@/lib/iam-admin/types';
import { NO_PROVIDERS, type InviteProviders } from '@/lib/invitations';
import { GROUP_KIND_LABELS, groupKind } from '@/lib/access-model/levels';
import type { AccessViewProps } from '../access-props';
import { PLATFORM, ownerOf } from '../access-scope';
import { offeredTo } from '../attachments/attach-form';
import { holdingRows, levelLabel, scopesOf } from '../holdings/holdings-model';
import { HoldingsTable } from '../holdings/holdings-table';
import { ConfirmDetach } from '../holdings/confirm-detach';
import { InstanceHeader } from '../instance-header';
import { AttachDialog, type AttachCandidate } from '../policies/attach-dialog';
import { useActionsAt, useContainerNames } from '../policies/policy-owners';
import '../holdings/holdings.css';
import '@/app/account/profile/profile.css';

const message = (e: unknown) => (e instanceof IamAdminError || e instanceof Error ? e.message : String(e));

const memberLabel = (p: PrincipalView) => p.display_name || p.email || p.name || p.id;

const KIND_LABEL: Record<string, string> = { user: 'Person', service_account: 'Service account', group: 'Group' };

// An IAM id typed for a member: a person's or a service account's.
const MEMBER_ID = /^(usr|sa)_[A-Za-z0-9]+$/;

type Member = { id: string; label: string; email?: string | null; kind?: PrincipalKind; joinedAt?: string | null };

/** The day a member joined, as Users shows it (`YYYY-MM-DD`); "—" when IAM did not keep it. */
function joinedDay(at: string | null | undefined): string {
  return at ? at.slice(0, 10) : '—';
}

/**
 * A group's page in Access › Groups, or the page of a group to be (`groupId` null, Create group):
 * its Info, its Members and its Policies (those it holds), as a person's page shows hers.
 * Members are added from a search (name and email shown) and removed after a confirmation;
 * policies are picked from a search of those IAM lets the caller attach here, several at once.
 * A group to be keeps what is picked until Create group: then it is made, its members join it
 * and its policies are attached at this level. A group owned elsewhere is shown as IAM lets the
 * caller read it, its members never changed here.
 */
export function GroupPage({
  api,
  can,
  scope,
  directory,
  nonce = 0,
  open,
  groupId,
  owned,
  loadProviders,
  onChanged,
  onCreated,
}: AccessViewProps & {
  /** Null: a group to be. */
  groupId: string | null;
  /** Owned by this scope: its members change here. One owned above is only attached to. */
  owned: boolean;
  loadProviders: () => Promise<InviteProviders>;
  onChanged: () => Promise<void>;
  /** A group to be, made: its page opens. */
  onCreated?: (id: string) => void;
}) {
  const isNew = groupId === null;
  const [group, setGroup] = useState<GroupView | null>(null);
  const [held, setHeld] = useState<AttachmentView[] | null>(isNew ? [] : null);
  const [candidates, setCandidates] = useState<Member[]>([]);
  const [attachable, setAttachable] = useState<AttachablePolicy[]>([]);
  const [providers, setProviders] = useState<InviteProviders>(NO_PROVIDERS);
  const [provider, setProvider] = useState('');
  const [claim, setClaim] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  // Which member's Remove asks for a confirmation now.
  const [confirming, setConfirming] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [draftMembers, setDraftMembers] = useState<Member[]>([]);
  const [draftPolicies, setDraftPolicies] = useState<AttachablePolicy[]>([]);
  const [dialog, setDialog] = useState<'members' | 'policies' | null>(null);
  const [creating, setCreating] = useState(false);
  const [madeId, setMadeId] = useState<string | null>(null);
  const mapsIdp = !isNew && (can('iam:MapIdpGroup') || can('iam:UnmapIdpGroup'));
  const changesMembers = isNew ? can('iam:CreateGroup') : owned;

  // Every attachment of the group, at every level: IAM lists those the caller may.
  const loadHeld = useCallback(async () => {
    if (!groupId) return;
    try {
      setHeld((await api.listAttachments({ principal_id: groupId })).items);
    } catch (e) {
      setHeld([]);
      setError(message(e));
    }
  }, [api, groupId]);
  const rows = useMemo(() => holdingRows(held ?? [], []), [held]);
  const scopes = useMemo(() => [...scopesOf(rows), group?.owner_scope ?? PLATFORM], [rows, group]);
  const here = ownerOf(scope);
  const names = useContainerNames(api, scopes, nonce);
  const actionsAt = useActionsAt(api, scopes, here, can, nonce);

  useEffect(() => {
    let cancelled = false;
    if (groupId) {
      api
        .getGroup(groupId)
        .then((g) => {
          if (cancelled) return;
          setGroup(g);
          setName(g.name ?? '');
          setDescription(g.description ?? '');
        })
        .catch((e) => !cancelled && setError(message(e)));
      void loadHeld();
    }
    // Whom the group may take: the scope's people, or, at the platform, every user and service
    // account for whoever may list them. Anyone else types an id.
    const people: Promise<Member[]> = scope.value
      ? directory
          .members(scope)
          .then((ms) => ms.map((m) => ({ id: m.userId, label: m.name || m.email || m.userId, email: m.email || null, kind: 'user' as const })))
      : can('iam:ListPrincipals')
        ? Promise.all([api.listPrincipals('user'), api.listPrincipals('service_account')]).then(([users, accounts]) =>
            [...users.items, ...accounts.items].map((p) => ({ id: p.id, label: memberLabel(p), email: p.email ?? null, kind: p.kind })),
          )
        : Promise.resolve([]);
    people.then((found) => !cancelled && setCandidates(found)).catch(() => undefined);
    // The policies it may hold here: those IAM lets the caller attach at this level.
    if (can('iam:AttachPolicy')) {
      api
        .attachable(scope.value ?? '')
        .then((found) => !cancelled && setAttachable(found.items.filter((p) => offeredTo(p, { id: groupId ?? 'grp_new', label: '', kind: 'group' }))))
        .catch(() => undefined);
    }
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
  }, [api, can, directory, scope, groupId, loadHeld, loadProviders, mapsIdp, nonce]);

  const run = async (call: () => Promise<GroupView>, done?: string) => {
    try {
      setGroup(await call());
      setError(null);
      setNotice(done ?? null);
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

  if (!isNew && !group) {
    return (
      <div className="access-group-detail">
        {error ? <p className="access-source-note" role="alert">{error}</p> : <p className="access-empty">Loading…</p>}
      </div>
    );
  }

  const members: Member[] = isNew
    ? draftMembers
    : group!.members.map((m) => ({ id: m.id, label: memberLabel(m), email: m.email ?? null, kind: m.kind, joinedAt: m.joined_at ?? null }));
  const inGroup = new Set(members.map((m) => m.id));
  const addable = candidates.filter((c) => !inGroup.has(c.id));
  const heldHere = new Set(
    isNew ? draftPolicies.map((p) => p.id) : (held ?? []).filter((a) => (a.scope ?? null) === (scope.value ?? null)).map((a) => a.policy_id),
  );
  const morePolicies = attachable.filter((p) => !heldHere.has(p.id));
  const kind = group ? GROUP_KIND_LABELS[groupKind(group)] : GROUP_KIND_LABELS.custom;

  const addMember = async (member: AttachCandidate) => {
    if (isNew) {
      setDraftMembers((current) => [...current, { id: member.id, label: member.label, email: member.email, kind: member.kind }]);
      setDialog(null);
      return;
    }
    const next = await api.addMember(group!.id, member.id);
    setGroup(next);
    setDialog(null);
    setError(null);
    setNotice(`${member.label} added to the group.`);
    await onChanged();
  };

  const removeMember = async (member: Member) => {
    setConfirming(null);
    if (isNew) {
      setDraftMembers((current) => current.filter((m) => m.id !== member.id));
      return;
    }
    await run(() => api.removeMember(group!.id, member.id), `${member.label} removed from the group.`);
  };

  const addPolicies = async (picked: { id: string }[]) => {
    const policies = attachable.filter((p) => picked.some((q) => q.id === p.id));
    if (isNew) {
      setDraftPolicies((current) => [...current, ...policies]);
      setDialog(null);
      return;
    }
    for (const policy of policies) {
      await api.attach({ policy_id: policy.id, principal_id: group!.id, scope: scope.value });
    }
    setDialog(null);
    setError(null);
    setNotice(policies.length === 1 ? `${policies[0].name} attached at ${scope.label}.` : `${policies.length} policies attached at ${scope.label}.`);
    await loadHeld();
  };

  const create = async () => {
    const value = name.trim();
    if (!value) return;
    setCreating(true);
    setError(null);
    let made: string | null = madeId;
    try {
      if (!made) {
        const what = description.trim();
        made = (
          await api.createGroup({
            name: value,
            ...(scope.value ? { scope: scope.value } : {}),
            ...(what ? { description: what } : {}),
          })
        ).id;
        setMadeId(made);
      }
      // What it grants first, then who holds it: each member joins a group that already holds
      // its policies, so joining is checked against them.
      for (const p of draftPolicies) await api.attach({ policy_id: p.id, principal_id: made, scope: scope.value });
      for (const m of draftMembers) await api.addMember(made, m.id);
      await onChanged();
      onCreated?.(made);
    } catch (e) {
      // Made, but a policy or a member was refused: said here, its page a click away.
      setError(made ? `The group was created, but: ${message(e)}` : message(e));
    } finally {
      setCreating(false);
    }
  };

  // Its name is what a group's Info changes (IAM keeps its owner, its kind and its id).
  const renames = !isNew && owned && can('iam:UpdateGroup');
  const nameChanged = !isNew && name.trim() !== '' && name.trim() !== (group!.name ?? '');
  const descriptionChanged = !isNew && description.trim() !== (group!.description ?? '');
  const save = async () => {
    setSaving(true);
    try {
      const changes: { name?: string; description?: string } = {};
      if (nameChanged) changes.name = name.trim();
      if (descriptionChanged) changes.description = description.trim();
      const renamed = await api.updateGroup(group!.id, changes);
      setGroup(renamed);
      setName(renamed.name ?? '');
      setDescription(renamed.description ?? '');
      setError(null);
      setNotice('Saved.');
      await onChanged();
    } catch (e) {
      setError(message(e));
    } finally {
      setSaving(false);
    }
  };

  const addButton = (label: string, action: string, onClick: () => void, disabled: boolean) => (
    <button type="button" className="org-settings-primary-button" onClick={onClick} disabled={disabled} data-action={action}>
      <Plus size={16} />
      {label}
    </button>
  );

  const nameFixed = !isNew && !renames;
  const ownerName = isNew ? scope.label : levelLabel(group!.owner_scope ?? PLATFORM, names);

  return (
    <div className="space-y-4" data-group-detail={group?.id ?? undefined} data-group-new={isNew ? '' : undefined}>
      {error && (
        <p className="access-source-note" role="alert">
          {error}{' '}
          {madeId && (
            <button type="button" className="access-holding-link" onClick={() => onCreated?.(madeId)}>
              Open the group
            </button>
          )}
        </p>
      )}
      {notice && (
        <p className="access-people-sub" role="status" data-group-notice="">
          {notice}
        </p>
      )}

      {/* The page's own top: its name, its id, what it is; Create or Save at its right. Info,
          below, has no title of its own. */}
      <InstanceHeader
        name={isNew ? name.trim() || 'New group' : group!.name}
        id={isNew ? null : group!.id}
        badge={
          <span className="platform-users-badge access-policy-badge" data-group-kind="">
            {kind}
          </span>
        }
        meta={
          <>
            <span>Owned by {ownerName}</span>
            {!isNew && !owned && <span>· read-only here: it changes at its level</span>}
          </>
        }
        actions={
          isNew ? (
            <button type="button" className="org-settings-primary-button" onClick={() => void create()} disabled={creating || !name.trim()} data-action="create">
              {creating ? 'Creating…' : 'Create group'}
            </button>
          ) : renames ? (
            <button type="button" className="org-settings-primary-button" onClick={() => void save()} disabled={saving || (!nameChanged && !descriptionChanged)} data-action="save">
              {saving ? 'Saving…' : 'Save'}
            </button>
          ) : undefined
        }
      />
      {isNew && <p className="text-sm text-muted-foreground">Name the group, then attach its policies and add its members below.</p>}

      <SettingsSection>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="group-name">
              Name
            </label>
            <input
              id="group-name"
              type="text"
              className={`account-profile-field-input${nameFixed ? ' account-profile-field-input-readonly' : ''}`}
              aria-label="Group name"
              placeholder="Its name, e.g. Analysts"
              maxLength={128}
              value={name}
              autoFocus={isNew}
              readOnly={nameFixed}
              aria-readonly={nameFixed || undefined}
              onChange={(e) => {
                setName(e.target.value);
                setNotice(null);
              }}
            />
          </div>
          <div className="account-profile-field access-group-description-field">
            <label className="account-profile-field-label" htmlFor="group-description">
              Description
            </label>
            <textarea
              id="group-description"
              className={`account-profile-field-input access-group-description${nameFixed ? ' account-profile-field-input-readonly' : ''}`}
              aria-label="Group description"
              placeholder={nameFixed ? '' : 'What the group is for, e.g. The analysts of the sales team'}
              maxLength={1000}
              rows={2}
              value={description}
              readOnly={nameFixed}
              aria-readonly={nameFixed || undefined}
              onChange={(e) => {
                setDescription(e.target.value);
                setNotice(null);
              }}
            />
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Policies"
        description={isNew ? `The policies it will hold, at ${scope.label}.` : 'The policies it holds, at every level you may list.'}
        actions={can('iam:AttachPolicy') ? addButton('Attach policies', 'add-policies', () => setDialog('policies'), creating || morePolicies.length === 0) : undefined}
      >
        {isNew ? (
          draftPolicies.length === 0 ? (
            <p className="text-sm text-muted-foreground">No policy yet.</p>
          ) : (
            <div className="access-table-wrap">
              <table className="access-table" aria-label="Policies">
                <thead>
                  <tr>
                    <th>Policy</th>
                    <th>Level</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {draftPolicies.map((p) => (
                    <tr key={p.id} data-policy={p.id}>
                      <td>{p.name}</td>
                      <td>{scope.label}</td>
                      <td className="text-right">
                        <button
                          type="button"
                          className="access-button"
                          aria-label={`Remove ${p.name}`}
                          onClick={() => setDraftPolicies((current) => current.filter((q) => q.id !== p.id))}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : held === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <HoldingsTable
            rows={rows}
            names={names}
            actionsAt={actionsAt}
            here={here}
            onDetach={(a) => void detach(a)}
            empty="Nothing you may list is attached to this group."
          />
        )}
      </SettingsSection>

      <SettingsSection
        title="Members"
        description={owned || isNew ? 'Who is in the group: each holds what it holds.' : 'Owned elsewhere: its members change at its level.'}
        actions={
          changesMembers && can('iam:AddGroupMember')
            ? addButton('Add member', 'add-members', () => setDialog('members'), creating)
            : undefined
        }
      >
        {members.length === 0 ? (
          <p className="text-sm text-muted-foreground">No members{isNew ? ' yet' : ''}.</p>
        ) : (
          <div className="access-table-wrap">
            <table className="access-table" aria-label="Members">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Kind</th>
                  {!isNew && <th>Joined at</th>}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id} data-member={m.id}>
                    <td>
                      {open?.person && m.kind !== 'group' && !isNew ? (
                        <button type="button" className="access-holding-link" aria-label={`Open ${m.label}`} onClick={() => open.person?.(m.id, m.label)}>
                          {m.label}
                        </button>
                      ) : (
                        <span>{m.label}</span>
                      )}
                      <span className="block text-xs text-muted-foreground">{m.email || m.id}</span>
                    </td>
                    <td>{KIND_LABEL[m.kind ?? 'user'] ?? m.kind}</td>
                    {!isNew && (
                      <td data-joined={m.joinedAt ?? ''} title={m.joinedAt ? undefined : 'Joined before IAM kept the date'}>
                        {joinedDay(m.joinedAt)}
                      </td>
                    )}
                    <td className="text-right">
                      {changesMembers && (isNew || can('iam:RemoveGroupMember')) &&
                        (isNew ? (
                          <button type="button" className="access-button" aria-label={`Remove ${m.label}`} disabled={creating} onClick={() => void removeMember(m)}>
                            Remove
                          </button>
                        ) : (
                          <ConfirmDetach
                            verb="Remove"
                            label={`Remove ${m.label}`}
                            confirming={confirming === m.id}
                            onAsk={() => setConfirming(m.id)}
                            onKeep={() => setConfirming(null)}
                            onConfirm={() => void removeMember(m)}
                          />
                        ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {mapsIdp && (
          <div className="mt-4 space-y-2" data-idp-mappings="">
            <p className="text-xs text-muted-foreground">
              Identity provider group claims: people whose provider sends one of them join this group when they sign in.
            </p>
            <ul className="access-group-list">
              {group!.idp_mappings.map((m) => (
                <li key={`${m.provider}/${m.claim_value}`} className="access-group-item" data-mapping={`${m.provider}/${m.claim_value}`}>
                  <span>
                    <span className="access-mono">{m.claim_value}</span> from {m.provider}
                  </span>
                  {can('iam:UnmapIdpGroup') && (
                    <button type="button" className="access-button" aria-label={`Unmap ${m.claim_value}`} onClick={() => void run(() => api.unmapIdpGroup(group!.id, m))}>
                      Remove
                    </button>
                  )}
                </li>
              ))}
              {group!.idp_mappings.length === 0 && <li className="access-empty">No mapping.</li>}
            </ul>
            {can('iam:MapIdpGroup') && (
              <form
                className="access-group-create"
                onSubmit={(e) => {
                  e.preventDefault();
                  const value = claim.trim();
                  if (!value || !provider) return;
                  void run(() => api.mapIdpGroup(group!.id, { provider, claim_value: value })).then(() => setClaim(''));
                }}
              >
                <select className="access-input" aria-label="Identity provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
                  {providers.providers.length === 0 && <option value="">No provider configured</option>}
                  {providers.providers.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.display_name || p.name}
                    </option>
                  ))}
                </select>
                <input className="access-input access-input-grow" aria-label="Group claim value" placeholder="Value of the group claim" value={claim} onChange={(e) => setClaim(e.target.value)} />
                <button type="submit" className="access-button access-button-primary" disabled={!claim.trim() || !provider}>
                  Map group
                </button>
              </form>
            )}
          </div>
        )}
      </SettingsSection>

      <AttachDialog
        open={dialog === 'members'}
        title="Add members"
        where={isNew ? 'the new group' : (group?.name ?? '')}
        description="Type a name, an email or an id: whom you pick joins the group."
        candidates={addable}
        typed={(id) => (MEMBER_ID.test(id) && !inGroup.has(id) ? { id, label: id, kind: id.startsWith('sa_') ? 'service_account' : 'user' } : null)}
        onClose={() => setDialog(null)}
        onAttach={addMember}
      />
      {dialog === 'policies' && (
        <RolePickerDialog
          open
          title="Attach policies"
          options={morePolicies.map((p) => ({ kind: 'policy' as const, id: p.id, name: p.name }))}
          onClose={() => setDialog(null)}
          onAdd={addPolicies}
        />
      )}
    </div>
  );
}
