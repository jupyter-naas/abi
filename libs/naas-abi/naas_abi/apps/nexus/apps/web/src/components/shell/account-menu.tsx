'use client';

import Link from 'next/link';
import { Building2, HelpCircle, LogOut, User } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore } from '@/stores/workspace';
import { getWorkspacePath } from './sidebar/utils';

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
  const canOrganizationSettings = useFeature('settings.organization');
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const helpHref = getWorkspacePath(currentWorkspaceId, '/help');

  return (
    <div
      role="menu"
      data-org-branded="true"
      className={cn('z-[300] min-w-56 w-64 rounded-lg border bg-card p-2 shadow-lg', className)}
      style={style}
    >
      <div className="border-b border-border/50 px-4 py-3">
        <p className="truncate font-medium" title={user?.name || 'User'}>
          {user?.name || 'User'}
        </p>
        <p className="min-w-0 truncate text-xs text-muted-foreground" title={user?.email || ''}>
          {user?.email || ''}
        </p>
      </div>

      <div className="py-2">
        <Link
          href="/account/profile"
          role="menuitem"
          onClick={onClose}
          className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
        >
          <User size={16} className="shrink-0 text-muted-foreground" />
          Account Settings
        </Link>
        {canOrganizationSettings && (
          <Link
            href="/organizations"
            role="menuitem"
            onClick={onClose}
            className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
          >
            <Building2 size={16} className="shrink-0 text-muted-foreground" />
            Organization Settings
          </Link>
        )}
        <Link
          href={helpHref}
          role="menuitem"
          onClick={onClose}
          className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
        >
          <HelpCircle size={16} className="shrink-0 text-muted-foreground" />
          Help
        </Link>
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
          className="flex w-full items-center gap-3 rounded-md px-4 py-2.5 text-sm text-destructive transition-colors hover:bg-destructive/10"
        >
          <LogOut size={16} className="shrink-0" />
          Log Out
        </button>
      </div>
    </div>
  );
}
