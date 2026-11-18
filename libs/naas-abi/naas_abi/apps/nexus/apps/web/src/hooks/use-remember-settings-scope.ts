'use client';

import { useEffect } from 'react';
import { rememberSettingsScopePath, settingsScopeFromPathname } from '@/lib/settings-scope-path';

/** Writes the current pathname into sessionStorage for its settings scope. */
export function useRememberSettingsScope(pathname: string | null | undefined): void {
  useEffect(() => {
    const scope = settingsScopeFromPathname(pathname);
    if (scope && pathname) {
      rememberSettingsScopePath(scope, pathname);
    }
  }, [pathname]);
}