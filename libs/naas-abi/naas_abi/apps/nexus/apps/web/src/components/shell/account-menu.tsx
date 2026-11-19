'use client';

import Link from 'next/link';
import { useEffect, useRef, type KeyboardEvent } from 'react';
import { Gauge, HelpCircle, LogOut, Settings, type LucideIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useAvatarSettingsLinks, type AvatarSettingsEntry } from '@/hooks/use-avatar-settings-links';
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

const ENABLED_ITEMS = '[role="menuitem"]:not([aria-disabled="true"])';

function enabledItems(panel: HTMLElement | null): HTMLElement[] {
  return panel ? [...panel.querySelectorAll<HTMLElement>(ENABLED_ITEMS)] : [];
}

function ItemLabel({ label }: { label: string }) {
  return <span className="account-menu-item-label">{label}</span>;
}

/** An entry of the menu that needs a right: a link, a muted row while it is read, or nothing. */
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
        <ItemLabel label={label} />
      </span>
    );
  }
  return (
    <Link href={entry.href} role="menuitem" onClick={onClose} className="account-menu-settings-item">
      <Icon size={14} className="shrink-0 text-muted-foreground" />
      <ItemLabel label={entry.label} />
    </Link>
  );
}

export function AccountMenuPanel({
  user,
  onClose,
  focusFirstItem = false,
  className,
  style,
}: {
  user: AccountMenuUser | null;
  onClose: () => void;
  /** Opened from the keyboard: the first item takes focus. From a pointer the panel
   *  does, so no link's URL pops up in the browser's corner. */
  focusFirstItem?: boolean;
  /** Position it (``fixed``) and set the corner it grows from (``origin-bottom-left``). */
  className?: string;
  style?: React.CSSProperties;
}) {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const logout = useAuthStore((s) => s.logout);
  const links = useAvatarSettingsLinks();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const helpHref = getWorkspacePath(currentWorkspaceId, '/help');

  // WAI-ARIA menu: focus is inside on open, the arrows move it.
  useEffect(() => {
    const target = focusFirstItem ? enabledItems(panelRef.current)[0] : panelRef.current;
    target?.focus({ preventScroll: true });
    // On open only: an entry that finishes loading later must not steal focus.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = enabledItems(panelRef.current);
    if (items.length === 0) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    const moveTo = (index: number) => {
      event.preventDefault();
      items[(index + items.length) % items.length].focus();
    };
    if (event.key === 'ArrowDown') moveTo(at + 1);
    else if (event.key === 'ArrowUp') moveTo(at < 0 ? items.length - 1 : at - 1);
    else if (event.key === 'Home') moveTo(0);
    else if (event.key === 'End') moveTo(items.length - 1);
  };

  return (
    <div
      ref={panelRef}
      role="menu"
      aria-label="Account"
      tabIndex={-1}
      data-org-branded="true"
      onKeyDown={onKeyDown}
      className={cn('account-menu-panel z-[10000] min-w-56 w-64 rounded-none border bg-card p-2 shadow-lg', className)}
      style={style}
    >
      <div className="account-menu-header">
        <UserAvatar user={user} className="h-8 w-8 shrink-0" alt="" />
        <div className="min-w-0">
          <p className="account-menu-header-name truncate font-medium" title={user?.name || 'User'}>
            {user?.name || 'User'}
          </p>
          <p className="account-menu-header-email truncate text-muted-foreground" title={user?.email || ''}>
            {user?.email || ''}
          </p>
        </div>
      </div>

      {/* Settings is one place, every level in its column (the dock's Settings opens it
          too); the Console is what the platform runs, for whoever may watch it. */}
      <div className="account-menu-group" role="group" aria-label="Settings">
        <Link href={links.settings.href} role="menuitem" onClick={onClose} className="account-menu-settings-item">
          <Settings size={14} className="shrink-0 text-muted-foreground" />
          <ItemLabel label={links.settings.label} />
        </Link>
        <SettingsScopeItem entry={links.console} label="Console" icon={Gauge} onClose={onClose} />
      </div>

      <div className="account-menu-group" role="group" aria-label="Session">
        <Link href={helpHref} role="menuitem" onClick={onClose} className="account-menu-settings-item">
          <HelpCircle size={14} className="shrink-0 text-muted-foreground" />
          <ItemLabel label="Help" />
        </Link>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            onClose();
            logout();
            router.push('/auth/login');
          }}
          className="account-menu-item account-menu-logout w-full"
        >
          <LogOut size={14} className="shrink-0" />
          <ItemLabel label="Log out" />
        </button>
      </div>
    </div>
  );
}
