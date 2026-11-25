'use client';

import type { ReactNode, Ref } from 'react';
import '@/app/account/profile/profile.css';
import './instance-header.css';

/**
 * The top of an instance's page (a group, a policy, a person), above its sections, as Settings
 * shows a workspace or an account: its picture at the left when it has one, its name, then its
 * id (and its slug when it has one), then what describes it (badges, a line). Its actions sit at
 * the right: the page has no header of the list above it.
 */
export function InstanceHeader({
  name,
  id,
  slug,
  badge,
  meta,
  image,
  imageAlt,
  actions,
  actionsRef,
}: {
  name: ReactNode;
  /** Null for an instance to be (not made yet). */
  id: string | null;
  slug?: string | null;
  /** What it is (a kind, Read only), beside its name. */
  badge?: ReactNode;
  /** A line describing it; nothing shown without. */
  meta?: ReactNode;
  image?: string | null;
  imageAlt?: string;
  actions?: ReactNode;
  /** Where other parts of the page put their actions (a portal's target), after `actions`. */
  actionsRef?: Ref<HTMLSpanElement>;
}) {
  const ids = [slug ? `/${slug}` : null, id].filter(Boolean).join(' · ');
  return (
    <div className="access-instance-header" data-instance-header="">
      <div className="account-profile-avatar-section access-instance-identity">
        {image && (
          <div className="account-profile-avatar-wrapper">
            {/* An uploaded picture or an external logo, as Settings shows them. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="account-profile-avatar-image access-instance-image" src={image} alt={imageAlt ?? ''} />
          </div>
        )}
        <div className="min-w-0">
          <div className="access-instance-title">
            <h2 className="account-profile-avatar-info-name access-instance-name" data-instance-name="">
              {name}
            </h2>
            {badge}
          </div>
          {ids && (
            <p className="account-profile-avatar-info-email access-instance-ids" data-instance-ids="">
              {ids}
            </p>
          )}
          {meta && (
            <div className="account-profile-avatar-info-hint access-instance-meta" data-instance-meta="">
              {meta}
            </div>
          )}
        </div>
      </div>
      {(actions || actionsRef) && (
        <div className="access-instance-actions">
          {actions}
          {actionsRef && <span ref={actionsRef} className="access-instance-actions-slot" data-policy-actions="" />}
        </div>
      )}
    </div>
  );
}
