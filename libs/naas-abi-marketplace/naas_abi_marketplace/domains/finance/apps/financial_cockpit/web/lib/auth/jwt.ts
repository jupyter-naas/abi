import { SignJWT, jwtVerify } from 'jose';

import type { PageId, SessionPayload } from '@/lib/types';
import { normalizePageId } from '@/lib/types';
import { MIN_SESSION_SECRET_LENGTH, configuredSecret } from '@/lib/auth/templateSecrets';

export const SESSION_COOKIE = 'asgard_session';
const SESSION_MAX_AGE = 60 * 60 * 24 * 7; // 7 days
const MAGIC_LINK_MAX_AGE = 60 * 15; // 15 minutes

function getSecret(): Uint8Array {
  // In production the template's value (or a short one) is no secret.
  const secret = configuredSecret(process.env.SESSION_SECRET, {
    minLength: MIN_SESSION_SECRET_LENGTH,
  });
  if (!secret) {
    throw new Error('SESSION_SECRET is not configured (run `npm run kickstart`)');
  }
  return new TextEncoder().encode(secret);
}

export async function createSessionToken(payload: SessionPayload): Promise<string> {
  return new SignJWT({ ...payload })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE}s`)
    .sign(getSecret());
}

export async function verifySessionToken(
  token: string,
): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getSecret());
    return {
      userId: String(payload.userId),
      displayName: String(payload.displayName),
      role:
        payload.role === 'owner'
          ? 'owner'
          : payload.role === 'admin'
            ? 'admin'
            : undefined,
      allowedEntities: (payload.allowedEntities as string[]) ?? [],
      allowedPages: ((payload.allowedPages as string[]) ?? [])
        .map((pageId) => normalizePageId(pageId))
        .filter((pageId): pageId is PageId => pageId !== null),
    };
  } catch {
    return null;
  }
}

export const SESSION_MAX_AGE_SECONDS = SESSION_MAX_AGE;

// Magic-link tokens are short-lived, single-purpose JWTs signed with the same
// secret. They carry only the userId; the session is built from config at
// verify time, so no permissions are trusted from the link itself.
export async function createMagicLinkToken(userId: string): Promise<string> {
  return new SignJWT({ userId, purpose: 'magic-link' })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(`${MAGIC_LINK_MAX_AGE}s`)
    .sign(getSecret());
}

export async function verifyMagicLinkToken(token: string): Promise<string | null> {
  try {
    const { payload } = await jwtVerify(token, getSecret());
    if (payload.purpose !== 'magic-link' || typeof payload.userId !== 'string') {
      return null;
    }
    return payload.userId;
  } catch {
    return null;
  }
}

export const MAGIC_LINK_MAX_AGE_SECONDS = MAGIC_LINK_MAX_AGE;
