'use client';

import Link from 'next/link';
import { Blocks, Building2, HelpCircle, LogOut, ShieldCheck, User, type LucideIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useAvatarSettingsLinks, type AvatarSettingsEntry } from '@/hooks/use-avatar-settings-links';
import { useOpensWorkspaceSettings } from '@/hooks/use-workspace-settings-access';
import { useWorkspaceStore } from '@/stores/workspace';
import { getWorkspacePath } from './sidebar/utils';
import './account-menu.css';

export type AccountMenuUser = {
  name?: string | null;
  email?: string | null;
  avatar?: string | null;
};

export function UserAvatar({
  user,
  className,
  alt,
}: {
  user: AccountMenuUser | null;
  className?: string;
  alt?: string;
}) {
  const name = user?.name || 'User';
  return (
    <span
      className={cn(
        'flex items-center justify-center overflow-hidden rounded-full',
        user?.avatar ? 'bg-transparent' : 'bg-primary text-primary-foreground',
        className,
      )}
    >
      {user?.avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={user.avatar} alt={alt ?? name} className="h-full w-full object-cover" />
      ) : (
        <span className="text-xs font-medium">{name.charAt(0) || 'U'}</span>
      )}
    </span>
  );
}

/** One settings scope of the menu: a link, a muted row while its access is read, or nothing. */
function SettingsScopeItem({
  entry,
  label,
  icon: Icon,
  onClose,
}: {
  entry: AvatarSettingsEntry;
  label: string;
  icon: LucideIcon;
  onClose: () => void;
}) {
  if (entry === null) return null;
  if (entry === 'loading') {
    return (
      <span
        role="menuitem"
        aria-disabled="true"
        aria-busy="true"
        className="account-menu-settings-item account-menu-settings-item-loading"
      >
        <Icon size={14} className="shrink-0 text-muted-foreground" />
        {label}
      </span>
    );
  }
  return (
    <Link href={entry.href} role="menuitem" onClick={onClose} className="account-menu-settings-item">
      <Icon size={14} className="shrink-0 text-muted-foreground" />
      {entry.label}
    </Link>
  );
}

export function AccountMenuPanel({
  user,
  onClose,
  className,
  style,
}: {
  user: AccountMenuUser | null;
  onClose: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const links = useAvatarSettingsLinks();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const helpHref = getWorkspacePath(currentWorkspaceId, '/help');
  // The workspace's architecture: for those who open its settings, as the sidebar was.
  const showInfrastructure = useOpensWorkspaceSettings() && !!currentWorkspaceId;
  const infrastructureHref = getWorkspacePath(currentWorkspaceId, '/settings/infrastructure');

  return (
    <div
      role="menu"
      data-org-branded="true"
      className={cn('account-menu-panel z-[10000] min-w-56 w-64 rounded-none border bg-card p-2 shadow-lg', className)}
      style={style}
    >
      <div className="account-menu-header border-b border-border/50">
        <p className="account-menu-header-name truncate font-medium" title={user?.name || 'User'}>
          {user?.name || 'User'}
        </p>
        <p className="account-menu-header-email min-w-0 truncate text-muted-foreground" title={user?.email || ''}>
          {user?.email || ''}
        </p>
      </div>

      <div className="account-menu-body">
        <div
          className="account-menu-settings-group border-b border-border/50"
          role="group"
          aria-label="Settings"
        >
          <Link
            href={links.account.href}
            role="menuitem"
            onClick={onClose}
            className="account-menu-settings-item"
          >
            <User size={14} className="shrink-0 text-muted-foreground" />
            {links.account.label}
          </Link>
          <SettingsScopeItem entry={links.organization} label="Organization" icon={Building2} onClose={onClose} />
          <SettingsScopeItem entry={links.platform} label="Platform" icon={ShieldCheck} onClose={onClose} />
        </div>
        <div className="account-menu-help-group" role="group" aria-label="Help">
          {showInfrastructure && (
            <Link
              href={infrastructureHref}
              role="menuitem"
              onClick={onClose}
              className="account-menu-settings-item"
            >
              <Blocks size={14} className="shrink-0 text-muted-foreground" />
              Infrastructure
            </Link>
          )}
          <Link
            href={helpHref}
            role="menuitem"
            onClick={onClose}
            className="account-menu-settings-item"
          >
            <HelpCircle size={14} className="shrink-0 text-muted-foreground" />
            Help
          </Link>
        </div>
      </div>

      <div className="border-t border-border/50 py-2">
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            onClose();
            logout();
            router.push('/auth/login');
          }}
          className="account-menu-item w-full text-destructive hover:bg-destructive/10"
        >
          <LogOut size={14} className="shrink-0" />
          Log Out
        </button>
      </div>
    </div>
  );
}
