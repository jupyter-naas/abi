'use client';

import { useEffect } from 'react';
import { startAuthSessionLifecycle } from '@/lib/auth-session-lifecycle';

export function AuthSessionManager() {
  useEffect(startAuthSessionLifecycle, []);
  return null;
}
