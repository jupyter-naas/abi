'use client';

import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { SettingsSection } from '@/components/settings/settings-ui';
import '@/app/account/profile/profile.css';
import './people.css';

/** Back to the list a person's page was opened from: the page is shown alone, with no header
 *  of the list (as a group's and a policy's). */
export function PersonBack({ label = 'Users', onClick }: { label?: string; onClick: () => void }) {
  return (
    <button type="button" className="access-person-back" data-action="back" onClick={onClick}>
      <ArrowLeft size={14} /> {label}
    </button>
  );
}

/**
 * A person's page first section: who it is about (their account's name and email, IAM's id),
 * read-only as Settings shows what cannot change here, and the page's actions (View as,
 * Reload…) at its right.
 */
export function PersonInfoSection({
  id,
  name,
  email,
  actions,
}: {
  id: string;
  /** Null while it is read. */
  name: string | null;
  email: string | null;
  actions?: ReactNode;
}) {
  const field = (key: string, label: string, value: string) => (
    <div className="account-profile-field">
      <label className="account-profile-field-label" htmlFor={`person-${key}`}>
        {label}
      </label>
      <input
        id={`person-${key}`}
        type="text"
        className="account-profile-field-input account-profile-field-input-readonly"
        aria-label={label}
        value={value}
        readOnly
        aria-readonly="true"
      />
    </div>
  );
  return (
    <SettingsSection
      title="Info"
      description="Their account names them: changed in their own profile, not here."
      actions={actions}
    >
      <div className="account-profile-form-grid" data-person-info={id}>
        {field('name', 'Name', name ?? 'Loading…')}
        {field('email', 'Email', email ?? '')}
        {field('id', 'ID', id)}
      </div>
    </SettingsSection>
  );
}
