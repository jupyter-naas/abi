'use client';

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { resentMessage, statusBadge, type MemberStatus } from '@/lib/people';

/** "Invited" beside someone created who has not signed in yet; nothing for anyone else. */
export function InvitedBadge({ status, className }: { status: MemberStatus | undefined; className?: string }) {
  const badge = statusBadge(status);
  if (!badge) return null;
  return (
    <Badge variant="primary" title={badge.title} className={cn('font-normal', className)} data-status="invited">
      {badge.label}
    </Badge>
  );
}

/**
 * Resend: emails an invited person their sign-in link again. Says what happened through
 * `onDone` (the message for the page's notice) or `onError`.
 */
export function ResendButton({
  email,
  resend,
  onDone,
  onError,
  className,
}: {
  email: string;
  /** True when the email was sent. */
  resend: () => Promise<boolean>;
  onDone: (message: string) => void;
  onError: (message: string) => void;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      data-action="resend"
      title={`Email ${email} a sign-in link again`}
      aria-label={`Resend the sign-in email to ${email}`}
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50',
        className
      )}
      onClick={async () => {
        setBusy(true);
        try {
          onDone(resentMessage(email, await resend()));
        } catch (error) {
          onError(error instanceof Error ? error.message : 'Failed to resend the sign-in email');
        } finally {
          setBusy(false);
        }
      }}
    >
      <RefreshCw size={12} className={busy ? 'animate-spin' : undefined} />
      {busy ? 'Sending…' : 'Resend'}
    </button>
  );
}
