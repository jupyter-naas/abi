'use client';

import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { InstanceHeader } from '../instance-header';
import '@/app/account/profile/profile.css';
import './people.css';
import { Card } from '@/components/ui/card';

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
 * A person's page top and first section: who it is about, as Settings shows an account (their
 * picture when they have one, their name, IAM's id, their email), the page's actions (View as,
 * Reload…) at its right; then Info, with no title of its own: their name and email,
 * read-only (their account names them, changed in their own profile); their id is above.
 */
export function PersonInfoSection({
  id,
  name,
  email,
  image,
  actions,
}: {
  id: string;
  /** Null while it is read. */
  name: string | null;
  email: string | null;
  image?: string | null;
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
    <>
      <InstanceHeader
        name={name ?? 'Loading…'}
        id={id}
        meta={email ? <span>{email}</span> : undefined}
        image={image}
        imageAlt={name ?? ''}
        actions={actions}
      />
      <Card>
        <div className="account-profile-form-grid" data-person-info={id}>
          {field('name', 'Name', name ?? 'Loading…')}
          {field('email', 'Email', email ?? '')}
        </div>
      </Card>
    </>
  );
}
