'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AlertCircle, Mail, UserPlus } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { OrgSettingsSectionCard } from '@/app/organizations/[orgId]/settings/components/org-settings-section-card';
import { inviteUser, listProviders, type Fetcher } from './users-api';
import { inviteSummary, PLATFORM_USERS_PATH, type InvitationProvider } from './users-model';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/organizations/[orgId]/settings/general/general.css';
import './users.css';

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Platform Settings › Users › Create user: someone added to the platform. Their
 * account is made at the identity provider when it does not exist yet, and they sign
 * in with what it sends them. Roles come from Roles & permissions, organizations from
 * each organization's Users.
 */
export function NewUser({ fetcher }: { fetcher?: Fetcher }) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [providers, setProviders] = useState<InvitationProvider[]>([]);
  const [provider, setProvider] = useState('');
  const [creating, setCreating] = useState(false);
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

  const address = email.trim();
  const ready = EMAIL.test(address) && !creating;

  const create = async () => {
    if (!ready) return;
    setCreating(true);
    setError(null);
    setSaid([]);
    const answer = await inviteUser(
      {
        email: address,
        ...(name.trim() ? { name: name.trim() } : {}),
        ...(providers.length > 1 && provider ? { provider } : {}),
      },
      fetcher
    );
    setCreating(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setSaid(inviteSummary(answer.data));
    setEmail('');
    setName('');
  };

  const managed = providers.find((p) => p.name === provider)?.managed_in_provider;

  return (
    <form
      className="platform-users-new-page"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void create();
      }}
    >
      <OrgSettingsPageHeader
        title="Create user"
        subtitle="Add someone to the platform: their account is made at the identity provider if it does not exist yet"
        actions={
          <span className="platform-users-new-actions">
            <Link href={PLATFORM_USERS_PATH} className="platform-users-new-cancel" data-action="cancel">
              {said.length > 0 ? 'Back to users' : 'Cancel'}
            </Link>
            <button type="submit" className="org-settings-primary-button" data-action="create" disabled={!ready}>
              <UserPlus size={16} />
              {creating ? 'Creating…' : 'Create user'}
            </button>
          </span>
        }
      />

      {error && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {said.length > 0 && (
        <div className="org-settings-users-alert" role="status">
          <Mail size={16} />
          <ul className="platform-users-outcome" data-field="invite-outcome">
            {said.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <OrgSettingsSectionCard padded>
        <div className="org-settings-card-heading">
          <UserPlus size={20} />
          <h3 className="org-settings-card-heading-title">User</h3>
        </div>
        <div className="org-settings-section-card-stack">
          <div className="org-settings-general-grid">
            <div className="org-settings-field">
              <label className="org-settings-field-label" htmlFor="new-user-email">
                Email *
              </label>
              <input
                id="new-user-email"
                data-field="invite-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@company.com"
                autoComplete="off"
                autoFocus
                className="org-settings-input"
              />
              {address && !EMAIL.test(address) ? (
                <p className="org-settings-field-hint">Enter an email address.</p>
              ) : null}
            </div>
            <div className="org-settings-field">
              <label className="org-settings-field-label" htmlFor="new-user-name">
                Full name
              </label>
              <input
                id="new-user-name"
                data-field="invite-name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="off"
                className="org-settings-input"
              />
              <p className="org-settings-field-hint">Used for a new account; an existing account keeps its name</p>
            </div>
          </div>
          {providers.length > 1 && (
            <div className="org-settings-field">
              <label className="org-settings-field-label" htmlFor="new-user-provider">
                Identity provider
              </label>
              <select
                id="new-user-provider"
                data-field="invite-provider"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
                className="org-settings-input"
              >
                {providers.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.display_name || p.name}
                  </option>
                ))}
              </select>
              {managed ? (
                <p className="org-settings-field-hint">
                  This provider manages its people: the person signs in with the account they have there.
                </p>
              ) : null}
            </div>
          )}
        </div>
      </OrgSettingsSectionCard>

      <p className="org-settings-footnote">
        Their roles are given in Roles &amp; permissions, and their organizations from each organization&apos;s
        Users page.
      </p>
    </form>
  );
}

export default function NewUserPage() {
  return <NewUser />;
}
