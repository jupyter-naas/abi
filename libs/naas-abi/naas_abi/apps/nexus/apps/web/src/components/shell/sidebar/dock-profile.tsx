'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useWarmAvatarSettingsLinks } from '@/hooks/use-avatar-settings-links';
import { ACCOUNT_SETTINGS_PATH, accountSettingsLabel, UserAvatar } from '../user-avatar';

/** The avatar at the bottom of the dock: it opens Settings on the Account tab. */
export function DockProfile({ labeled }: { labeled: boolean }) {
  const [mounted, setMounted] = useState(false);
  const user = useAuthStore((s) => s.user);
  // The Settings tabs' access reads start now, not when Settings opens.
  useWarmAvatarSettingsLinks();
  const displayUser = mounted ? user : null;
  const name = displayUser?.name || 'User';

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <Link
      href={ACCOUNT_SETTINGS_PATH}
      aria-label={accountSettingsLabel(displayUser?.name)}
      className={cn(
        'flex items-center rounded-lg outline-none focus-visible:ring-0',
        'hover:bg-workspace-accent-10',
        labeled ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center',
      )}
    >
      <UserAvatar user={displayUser} className="h-8 w-8 flex-shrink-0" alt="" />
      {labeled && (
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{name}</span>
      )}
    </Link>
  );
}
