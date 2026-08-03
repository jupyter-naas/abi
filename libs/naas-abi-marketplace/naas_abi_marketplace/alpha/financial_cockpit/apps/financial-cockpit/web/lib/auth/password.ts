import 'server-only';
import { timingSafeEqual } from 'node:crypto';

import { loadConfig } from '@/lib/config/loadConfig';
import type { SessionPayload } from '@/lib/types';
import { isOwnerRole } from '@/lib/types';

/**
 * Password sign-in — the template's single shared login. The root password is
 * stored as the `ROOT_PASSWORD` secret and grants a full-access OWNER session:
 * it maps to the owner declared in config.yaml, so owner protections (isOwner,
 * read-only in the user manager) apply. There is no e-mail / magic-link path.
 */

/** Constant-time compare to avoid leaking length/contents via timing. */
function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, 'utf-8');
  const bb = Buffer.from(b, 'utf-8');
  if (ab.length !== bb.length) {
    // Still run a compare to keep timing roughly constant on length mismatch.
    timingSafeEqual(ab, ab);
    return false;
  }
  return timingSafeEqual(ab, bb);
}

/** Resolve the full-access owner session from the shared root password, or null. */
export function verifyPassword(password: string): SessionPayload | null {
  const root = process.env.ROOT_PASSWORD;
  if (!root || !safeEqual(password, root)) {
    return null;
  }
  // Map the shared login to the configured owner so it *is* the protected root
  // identity (owner protections apply). Falls back to a synthetic id if config
  // somehow declares no owner.
  const owner = (loadConfig().users ?? []).find((u) => isOwnerRole(u.role));
  return {
    userId: owner?.user_id ?? 'pwd:owner',
    displayName: owner?.name ?? 'Owner',
    role: 'owner',
    allowedEntities: [],
    allowedPages: [],
  };
}
