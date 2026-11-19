'use client';

import './system.css';
import '@/app/organizations/[orgId]/settings/users/users.css';

import { RefreshCw } from 'lucide-react';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';

/** A page's Refresh, the header's icon button: reloads what it shows, beyond its own polling. */
export function SystemRefresh({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="org-settings-users-secondary-button"
      data-action="refresh"
      onClick={onClick}
      title="Refresh"
      aria-label="Refresh"
    >
      <RefreshCw size={16} />
    </button>
  );
}

/**
 * A page of the Platform Settings shell that fills its height: the title, its
 * actions, then a body that scrolls (or lays out its own panes when `flush`).
 */
export function SystemFrame({
  title,
  subtitle,
  badge,
  actions,
  flush = false,
  children,
}: {
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="system-page">
      <div className="system-page-header">
        <OrgSettingsPageHeader title={title} subtitle={subtitle} badge={badge} actions={actions} />
      </div>
      <div className={flush ? 'system-body system-body-flush' : 'system-body'}>{children}</div>
    </div>
  );
}
