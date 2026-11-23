'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, ArrowLeft, Camera, Mail, UserPlus, X } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { CapabilityGroupPicker, type CapabilityGroupsAt } from '@/components/invitations/invite-policy-picker';
import { useInviteProviders } from '@/components/invitations/use-invite-providers';
import { providerHint } from '@/lib/invitations';
import {
  LEVELS,
  LEVEL_EVERYWHERE_NOTE,
  LEVEL_LABELS,
  createPeopleApi,
  looksLikeEmail,
  type CapabilityGroup,
  type CreatedPerson,
  type Level,
  type PeopleApi,
  type PeopleProfile,
} from '@/lib/people';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { AccountSectionCard } from '@/app/account/components/account-section-card';
import {
  PROFILE_FIELDS,
  createUserRequest,
  initialOrganizationId,
  organizationReadOnly,
  selectedOrganization,
  workspaceGrants,
  type CreateUserDraft,
  type CreateUserRequest,
  type OrganizationProp,
  type WorkspaceChoice,
} from './create-user-form-model';
import '@/app/account/profile/profile.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

const BIO_MAX_LENGTH = 2000;
const AVATAR_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
const AVATAR_MAX_BYTES = 2 * 1024 * 1024;

async function fetchOrganizationWorkspaces(organizationId: string): Promise<WorkspaceChoice[] | 'forbidden'> {
  const { authFetch } = await import('@/stores/auth');
  const res = await authFetch(`/api/organizations/${encodeURIComponent(organizationId)}/workspaces`);
  if (res.status === 403) return 'forbidden';
  if (!res.ok) return [];
  const data = (await res.json()) as { id: string; name: string }[];
  return Array.isArray(data) ? data.map((w) => ({ id: w.id, name: w.name })) : [];
}

async function uploadOrganizationAvatar(organizationId: string, userId: string, file: File): Promise<void> {
  const { useOrganizationStore } = await import('@/stores/organization');
  await useOrganizationStore.getState().uploadMemberAvatar(organizationId, userId, file);
}

export type CreateUserFormProps = {
  /** The organization: fixed (read-only), or picked among choices. */
  organization: OrganizationProp;
  /** The workspace the person joins, shown read-only (Workspace settings › Members › New). */
  attachedWorkspace?: WorkspaceChoice;
  /** The organization page: the org admin toggle and the organization's workspaces to pick. */
  organizationRoute: boolean;
  prefill?: { email?: string; name?: string };
  subtitle: string;
  back: { href: string; label: string };
  /**
   * After the person is created (or linked): navigate, or return a message to show (the form
   * is then emptied for the next one).
   */
  onCreated: (created: CreatedPerson, request: CreateUserRequest) => string | void | Promise<string | void>;
  onCancel: () => void;
  /** The caller may not list the organization's workspaces (the org page leaves then). */
  onForbidden?: () => void;
  /** Tests pass fakes. */
  api?: Pick<PeopleApi, 'createInWorkspace' | 'createInOrganization'>;
  loadWorkspaces?: (organizationId: string) => Promise<WorkspaceChoice[] | 'forbidden'>;
  uploadAvatar?: (organizationId: string, userId: string, file: File) => Promise<void>;
  loadCapabilities?: (at: CapabilityGroupsAt) => Promise<CapabilityGroup[]>;
};

function emptyDraft(prefill?: { email?: string; name?: string }): CreateUserDraft {
  return {
    email: prefill?.email ?? '',
    name: prefill?.name ?? '',
    level: 'member',
    orgAdmin: false,
    workspaces: [],
    attachedAdmin: false,
    capabilities: [],
    profile: {},
  };
}

/**
 * Create user: the form Organization settings › Users › New and Workspace settings › Members ›
 * New share. The person is created at once (invited until they first sign in), or linked when
 * the email already has an account; the answer is the same either way. One request carries their
 * level (in all their workspaces), the org admin toggle, every workspace with "admin", and the
 * capability groups (#1589).
 */
export function CreateUserForm({
  organization,
  attachedWorkspace,
  organizationRoute,
  prefill,
  subtitle,
  back,
  onCreated,
  onCancel,
  onForbidden,
  api,
  loadWorkspaces = fetchOrganizationWorkspaces,
  uploadAvatar = uploadOrganizationAvatar,
  loadCapabilities,
}: CreateUserFormProps) {
  const client = useMemo(() => api ?? createPeopleApi(), [api]);
  const providers = useInviteProviders(true);
  const [draft, setDraft] = useState<CreateUserDraft>(() => emptyDraft(prefill));
  const [organizationId, setOrganizationId] = useState<string | null>(() => initialOrganizationId(organization));
  const [workspaces, setWorkspaces] = useState<WorkspaceChoice[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [creating, setCreating] = useState(false);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // The org route: the org admin toggle, the organization's workspaces to pick, an org picture.
  const org = selectedOrganization(organization, organizationId);
  const capabilitiesAt: CapabilityGroupsAt | null = organizationRoute
    ? organizationId
      ? { organizationId }
      : null
    : attachedWorkspace
      ? { workspaceId: attachedWorkspace.id }
      : null;

  useEffect(() => {
    if (!avatarFile) {
      setAvatarPreview('');
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setAvatarPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  // The page's callbacks, read when the list answers: the list is read again only when the
  // organization changes, not each time the page renders new callbacks.
  const loaders = useRef({ loadWorkspaces, onForbidden });
  loaders.current = { loadWorkspaces, onForbidden };

  useEffect(() => {
    setWorkspaces([]);
    if (!organizationRoute || !organizationId) return;
    let cancelled = false;
    loaders.current
      .loadWorkspaces(organizationId)
      .then((found) => {
        if (cancelled) return;
        if (found === 'forbidden') loaders.current.onForbidden?.();
        else setWorkspaces(found);
      })
      .catch(() => {
        // The workspace list is optional here; they are assigned later from the Users table.
      });
    return () => {
      cancelled = true;
    };
  }, [organizationRoute, organizationId]);

  const sortedWorkspaces = useMemo(
    () => workspaces.filter((w) => w.id !== attachedWorkspace?.id).sort((a, b) => a.name.localeCompare(b.name)),
    [workspaces, attachedWorkspace?.id]
  );
  const grants = workspaceGrants(draft, attachedWorkspace);
  const emailValid = looksLikeEmail(draft.email);
  const showAvatar = organizationRoute;

  const set =
    (field: 'email' | 'name') => (event: React.ChangeEvent<HTMLInputElement>) =>
      setDraft((current) => ({ ...current, [field]: event.target.value }));
  const setProfile =
    (field: keyof PeopleProfile) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const value = field === 'bio' ? event.target.value.slice(0, BIO_MAX_LENGTH) : event.target.value;
      setDraft((current) => ({ ...current, profile: { ...current.profile, [field]: value } }));
    };

  const toggleWorkspace = (id: string) =>
    setDraft((current) => ({
      ...current,
      workspaces: current.workspaces.some((w) => w.id === id)
        ? current.workspaces.filter((w) => w.id !== id)
        : [...current.workspaces, { id, admin: false }],
    }));
  const setWorkspaceAdmin = (id: string, admin: boolean) =>
    setDraft((current) => ({
      ...current,
      workspaces: current.workspaces.map((w) => (w.id === id ? { ...w, admin } : w)),
    }));

  const pickAvatar = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!AVATAR_TYPES.includes(file.type)) {
      setError('Please choose a PNG, JPG, GIF or WEBP image.');
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      setError('The picture must be less than 2MB.');
      return;
    }
    setError('');
    setAvatarFile(file);
  };

  const handleCreate = async () => {
    const built = createUserRequest(
      { ...draft, provider: providers.providerToSend() },
      { organization, organizationId, attachedWorkspace, organizationRoute }
    );
    if (!built.ok) {
      setError(built.error);
      return;
    }
    const { request } = built;
    setError('');
    setNotice('');
    setCreating(true);
    try {
      const created =
        request.route === 'workspace'
          ? await client.createInWorkspace(request.workspaceId, request.body)
          : await client.createInOrganization(request.organizationId, request.body);
      // The org picture needs someone of the organization's directory.
      if (avatarFile && request.route === 'organization' && created.member) {
        try {
          await uploadAvatar(request.organizationId, created.user.id, avatarFile);
        } catch (err) {
          throw new Error(
            `User created, but the picture could not be uploaded: ${
              err instanceof Error ? err.message : 'unknown error'
            }. Upload it from their page.`
          );
        }
      }
      const message = await onCreated(created, request);
      if (typeof message === 'string') {
        setNotice(message);
        setDraft(emptyDraft());
        setAvatarFile(null);
      }
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to create the user');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="account-profile-page" data-create-user-form>
      <Link href={back.href} className="org-member-detail-back">
        <ArrowLeft size={14} />
        {back.label}
      </Link>

      <AccountPageHeader
        title="Create user"
        subtitle={subtitle}
        actions={
          <div className="org-member-detail-actions">
            <button type="button" onClick={onCancel} className="org-member-detail-cancel-button">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!emailValid || creating}
              className="account-profile-save-button"
              data-action="create"
            >
              <UserPlus size={16} />
              {creating ? 'Creating...' : 'Create user'}
            </button>
          </div>
        }
      />

      {error && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="org-settings-users-alert" role="status">
          <Mail size={16} />
          <span>{notice}</span>
        </div>
      )}

      {providerHint(providers.chosen) && <p className="org-settings-footnote">{providerHint(providers.chosen)}</p>}

      {showAvatar && (
        <div className="account-profile-avatar-section">
          <div className="account-profile-avatar-wrapper">
            <input
              ref={fileInputRef}
              type="file"
              accept={AVATAR_TYPES.join(',')}
              onChange={pickAvatar}
              className="account-profile-avatar-input"
            />
            {avatarPreview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarPreview} alt="" className="account-profile-avatar-image" />
            ) : (
              <div className="account-profile-avatar-placeholder">
                {(draft.name || draft.email || '?').charAt(0).toUpperCase()}
              </div>
            )}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={creating}
              className="account-profile-avatar-upload-button"
              title="Choose a picture"
            >
              <Camera size={16} />
            </button>
          </div>
          <div>
            <h3 className="account-profile-avatar-info-name">{draft.name.trim() || 'New user'}</h3>
            <p className="account-profile-avatar-info-email">{draft.email.trim()}</p>
            <p className="account-profile-avatar-info-hint">
              Organization picture (max 2MB), uploaded when the user is created. Their account shows it when it
              has no picture.
            </p>
            {avatarFile ? (
              <button type="button" onClick={() => setAvatarFile(null)} className="account-profile-avatar-remove-button">
                <X size={12} />
                Remove picture
              </button>
            ) : null}
          </div>
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
              value={draft.email}
              onChange={set('email')}
              placeholder="name@company.com"
              className="account-profile-field-input"
              autoFocus={!draft.email}
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-name">
              Full name
            </label>
            <input
              id="create-user-name"
              type="text"
              value={draft.name}
              onChange={set('name')}
              placeholder="Used for a new account; an existing account keeps its name"
              className="account-profile-field-input"
            />
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-org">
              Organization
            </label>
            {organizationReadOnly(organization) ? (
              <input
                id="create-user-org"
                type="text"
                value={org?.name || org?.id || 'No organization'}
                readOnly
                aria-readonly
                className="account-profile-field-input"
                data-field="organization"
              />
            ) : (
              <select
                id="create-user-org"
                value={organizationId ?? ''}
                onChange={(event) => {
                  setOrganizationId(event.target.value || null);
                  setDraft((current) => ({ ...current, workspaces: [] }));
                }}
                className="account-profile-field-input"
                data-field="organization"
              >
                {'choices' in organization &&
                  organization.choices.map((choice) => (
                    <option key={choice.id} value={choice.id}>
                      {choice.name}
                    </option>
                  ))}
              </select>
            )}
          </div>
          <div className="account-profile-field">
            <label className="account-profile-field-label" htmlFor="create-user-level">
              Level
            </label>
            <select
              id="create-user-level"
              value={draft.level}
              onChange={(event) => setDraft((current) => ({ ...current, level: event.target.value as Level }))}
              className="account-profile-field-input"
              data-field="level"
            >
              {LEVELS.map((level) => (
                <option key={level} value={level}>
                  {LEVEL_LABELS[level]}
                </option>
              ))}
            </select>
            <p className="org-settings-footnote" data-level-note>
              {LEVEL_EVERYWHERE_NOTE}
            </p>
          </div>
          {organizationRoute && (
            <div className="account-profile-field" data-field="org-admin">
              <span className="account-profile-field-label">Organization</span>
              <Checkbox
                label="Org admin: reaches every workspace of the organization"
                checked={draft.orgAdmin}
                onCheckedChange={(on) => setDraft((current) => ({ ...current, orgAdmin: on }))}
                disabled={creating}
              />
            </div>
          )}
          {attachedWorkspace && (
            <div className="account-profile-field" data-field="workspace-admin">
              <span className="account-profile-field-label">Workspace</span>
              <Checkbox
                label={`Admin of ${attachedWorkspace.name}`}
                checked={draft.attachedAdmin}
                onCheckedChange={(on) => setDraft((current) => ({ ...current, attachedAdmin: on }))}
                disabled={creating}
              />
            </div>
          )}
          {providers.choosable && (
            <div className="account-profile-field">
              <label className="account-profile-field-label" htmlFor="create-user-provider">
                Identity provider
              </label>
              <select
                id="create-user-provider"
                value={providers.picked ?? ''}
                onChange={(event) => providers.setPicked(event.target.value)}
                className="account-profile-field-input"
              >
                {providers.known.providers.map((provider) => (
                  <option key={provider.name} value={provider.name}>
                    {provider.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {PROFILE_FIELDS.map(({ field, label }) => (
            <div key={field} className="account-profile-field">
              <label className="account-profile-field-label" htmlFor={`create-user-${field}`}>
                {label}
              </label>
              <input
                id={`create-user-${field}`}
                type="text"
                value={draft.profile[field] ?? ''}
                onChange={setProfile(field)}
                placeholder={label}
                className="account-profile-field-input"
              />
            </div>
          ))}
        </div>
        <div className="account-profile-field">
          <div className="account-profile-bio-header">
            <label className="account-profile-field-label" htmlFor="create-user-bio">
              Bio
            </label>
            <span className="account-profile-bio-count">
              {(draft.profile.bio ?? '').length} / {BIO_MAX_LENGTH}
            </span>
          </div>
          <textarea
            id="create-user-bio"
            value={draft.profile.bio ?? ''}
            onChange={setProfile('bio')}
            placeholder="Bio in this organization"
            rows={6}
            maxLength={BIO_MAX_LENGTH}
            className="account-profile-field-textarea"
          />
        </div>
        <CapabilityGroupPicker
          at={capabilitiesAt}
          value={draft.capabilities}
          onChange={(capabilities) => setDraft((current) => ({ ...current, capabilities }))}
          disabled={creating}
          {...(loadCapabilities ? { load: loadCapabilities } : {})}
        />
      </AccountSectionCard>

      {organizationRoute && (
        <section className="org-member-detail-section">
          <header className="org-member-detail-section-header">
            <h3>
              Workspaces <span className="org-member-detail-count">{grants.length}</span>
            </h3>
            <p>
              The workspaces they work in, at their level, and those they administer. Org admins reach every
              workspace of the organization anyway; someone in no workspace is one of the organization&apos;s
              people.
            </p>
          </header>
          <div className="org-settings-users-table-wrap org-create-user-workspaces">
            {sortedWorkspaces.length === 0 ? (
              <p className="org-settings-users-no-match">No workspace in this organization.</p>
            ) : (
              <ul>
                {sortedWorkspaces.map((workspace) => {
                  const picked = draft.workspaces.find((w) => w.id === workspace.id);
                  return (
                    <li key={workspace.id} data-workspace={workspace.id}>
                      <label>
                        <Checkbox checked={!!picked} onCheckedChange={() => toggleWorkspace(workspace.id)} />
                        <span>{workspace.name}</span>
                      </label>
                      {picked && (
                        <span data-field="workspace-admin">
                          <Checkbox
                            label="Admin"
                            aria-label={`Admin of ${workspace.name}`}
                            checked={picked.admin}
                            onCheckedChange={(on) => setWorkspaceAdmin(workspace.id, on)}
                            disabled={creating}
                          />
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
