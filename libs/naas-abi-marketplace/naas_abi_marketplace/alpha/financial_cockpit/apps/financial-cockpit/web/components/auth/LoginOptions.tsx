'use client';

import { PasswordForm } from './PasswordForm';

/**
 * Sign-in for the local template: a single shared demo password grants a
 * full-access admin session. No e-mail / magic-link service is involved — set
 * ADMIN_PASSWORD in .env (see .env.example) to enable it.
 */
export function LoginOptions() {
  return <PasswordForm />;
}
