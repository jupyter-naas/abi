'use client';

import { cn } from '@/lib/utils';

export type AvatarUser = {
  name?: string | null;
  email?: string | null;
  avatar?: string | null;
};

/** Account settings. The account menu's Account row, and the page Settings falls back to. */
export const ACCOUNT_SETTINGS_PATH = '/account/profile';

export function UserAvatar({
  user,
  className,
  alt,
}: {
  user: AvatarUser | null;
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
