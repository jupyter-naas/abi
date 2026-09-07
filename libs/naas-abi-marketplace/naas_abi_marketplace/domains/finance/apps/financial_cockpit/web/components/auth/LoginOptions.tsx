'use client';

import { PasswordForm } from './PasswordForm';

/**
 * Sign-in for the local template: a single shared root password grants a
 * full-access owner session. No e-mail / magic-link service is involved — set
 * ROOT_PASSWORD in .env (see .env.example) to enable it.
 */
export function LoginOptions() {
  return <PasswordForm />;
}
