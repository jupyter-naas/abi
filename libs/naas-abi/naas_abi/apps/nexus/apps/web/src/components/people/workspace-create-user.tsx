'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, ArrowLeft, UserPlus } from 'lucide-react';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import { createPeopleApi, looksLikeEmail, type CreatedPerson, type PeopleApi } from '@/lib/people';
import {
  createMemberRolesApi,
  defaultRole,
  roleProblem,
  type MemberRolesApi,
  type RoleOptions,
  type RoleSelection,
} from '@/lib/member-roles';
import { RoleEditor } from './role-editor';
import '@/app/account/profile/profile.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

const NO_OPTIONS: RoleOptions = { groups: [], policies: [] };

/** What the create request carries of the Role: the level and the admins group. */
export function createdAccess(options: RoleOptions, role: RoleSelection): { level: 'member' | 'viewer' | null; admin: boolean } {
  const chosen = options.groups.filter((g) => role.groups.includes(g.id));
  const level = chosen.find((g) => g.kind === 'level')?.level ?? null;
  return { level, admin: chosen.some((g) => g.kind === 'admins') };
}

/**
 * Create user (Workspace settings › Users › Create user): their email, their full name, and
 * their Role here: Members and the workspace's own group to start with, groups and policies
 * added or removed. The person is created at once (invited until they first sign in), or
 * linked when the email already has an account; then their Role is made what was picked.
 */
export function WorkspaceCreateUserForm({
  workspaceId,
  workspaceName,
  prefill,
  back,
  onCreated,
  onCancel,
  api,
  rolesApi,
}: {
  workspaceId: string;
  workspaceName: string;
  prefill?: { email?: string; name?: string };
  /** Where "← Users" goes. */
  back: { href: string; label: string };
  /** `warning`: created, but something to say (their Role not all made). */
  onCreated: (created: CreatedPerson, warning: string | null) => void;
  onCancel: () => void;
  api?: Pick<PeopleApi, 'createInWorkspace'>;
  rolesApi?: Pick<MemberRolesApi, 'options' | 'set'>;
}) {
  const people = useMemo(() => api ?? createPeopleApi(), [api]);
  const roles = useMemo(() => rolesApi ?? createMemberRolesApi(), [rolesApi]);
  const scope = useMemo(() => ({ kind: 'workspace' as const, id: workspaceId }), [workspaceId]);
  const [email, setEmail] = useState(prefill?.email ?? '');
  const [name, setName] = useState(prefill?.name ?? '');
  const [options, setOptions] = useState<RoleOptions>(NO_OPTIONS);
  const [role, setRole] = useState<RoleSelection>({ groups: [], policies: [] });
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let live = true;
    roles
      .options(scope)
      .then((found) => {
        if (!live) return;
        setOptions(found);
        setRole(defaultRole(found));
      })
      .catch((e: unknown) => live && setLoadError(e instanceof Error ? e.message : 'Could not load the roles'));
    return () => {
      live = false;
    };
  }, [roles, scope]);

  const submit = async () => {
    setError('');
    if (!looksLikeEmail(email.trim())) {
      setError('Enter a valid email address.');
      return;
    }
    const problem = roleProblem(options, role);
    if (problem) {
      setError(problem);
      return;
    }
    setCreating(true);
    try {
      const access = createdAccess(options, role);
      const created = await people.createInWorkspace(workspaceId, {
        email: email.trim(),
        name: name.trim() || undefined,
        level: access.level,
        admin: access.admin,
        capabilities: [],
      });
      let warning: string | null = null;
      try {
        await roles.set(scope, created.user.id, role);
      } catch (e) {
        warning = `${created.user.name || created.user.email} was added to ${workspaceName}, but their Role is not all made: ${
          e instanceof Error ? e.message : 'unknown error'
        }. Open their page to finish it.`;
      }
      onCreated(created, warning);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create the user');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="account-profile-page" data-workspace-create-user>
      <Link href={back.href} className="org-member-detail-back">
        <ArrowLeft size={14} />
        {back.label}
      </Link>

      <AccountPageHeader
        title="Create user"
        subtitle={`Add someone to ${workspaceName}. They are created at once and invited until they first sign in; an email that already has an account is linked to it.`}
        actions={
          <div className="org-member-detail-actions">
            <button type="button" onClick={onCancel} disabled={creating} className="org-member-detail-cancel-button">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              disabled={creating || !!loadError}
              className="account-profile-save-button"
              data-action="create"
            >
              <UserPlus size={16} />
              {creating ? 'Creating…' : 'Create user'}
            </button>
          </div>
        }
      />

      {(loadError || error) && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{loadError || error}</span>
        </div>
      )}

      <AccountSectionCard padded stack>
        <div className="account-profile-form-grid">
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-email">
              Email
            </label>
            <input
              id="create-user-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="account-profile-field-input"
              autoFocus={!email}
              data-field="email"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-name">
              Full name
            </label>
            <input
              id="create-user-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Used for a new account; an existing account keeps its name"
              className="account-profile-field-input"
              data-field="name"
            />
          </div>
        </div>
        <div className="account-profile-field" data-field="role">
          <span className="account-profile-field-label">Role</span>
          <RoleEditor options={options} value={role} onChange={setRole} disabled={creating} />
        </div>
      </AccountSectionCard>
    </div>
  );
}
