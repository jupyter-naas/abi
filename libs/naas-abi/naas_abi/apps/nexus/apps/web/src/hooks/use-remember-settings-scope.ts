'use client';

import { useEffect } from 'react';
import { rememberSettingsPath } from '@/lib/settings-scope-path';

/** Writes the current pathname into sessionStorage as the last Settings page, and its level's. */
export function useRememberSettingsPath(pathname: string | null | undefined): void {
  useEffect(() => {
    if (pathname) rememberSettingsPath(pathname);
  }, [pathname]);
}
