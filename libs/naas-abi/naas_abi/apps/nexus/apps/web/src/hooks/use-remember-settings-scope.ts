'use client';

import { useEffect } from 'react';
import { rememberSettingsPath, type SettingsArea } from '@/lib/settings-scope-path';

/** Writes the current pathname into sessionStorage as the last page of its area. */
export function useRememberSettingsPath(pathname: string | null | undefined, area: SettingsArea = 'settings'): void {
  useEffect(() => {
    if (pathname) rememberSettingsPath(area, pathname);
  }, [pathname, area]);
}
