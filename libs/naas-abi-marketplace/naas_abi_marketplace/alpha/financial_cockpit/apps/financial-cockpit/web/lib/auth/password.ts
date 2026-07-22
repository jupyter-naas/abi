import 'server-only';
import { timingSafeEqual } from 'node:crypto';

import type { SessionPayload } from '@/lib/types';

/**
 * Password sign-in — a secondary option alongside the magic link, added because
 * the magic-link e-mail is unreliable for internal recipients (Microsoft
 * Defender quarantines the login link). A single shared admin password is stored
 * as the `ADMIN_PASSWORD` secret and grants a full-access admin session.
 *
 * The synthesised `userId` (`pwd:admin`) is only a stable session key — admins
 * are authorised by `role`, never by a per-user config lookup.
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

/** Resolve a full-access admin session from the shared password, or null. */
export function verifyPassword(password: string): SessionPayload | null {
  const admin = process.env.ADMIN_PASSWORD;
  if (!admin || !safeEqual(password, admin)) {
    return null;
  }
  return {
    userId: 'pwd:admin',
    displayName: 'Administrateur',
    role: 'admin',
    allowedEntities: [],
    allowedPages: [],
  };
}
