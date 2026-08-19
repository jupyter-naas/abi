'use client';

import { ThemeSwitch } from '@/components/ui/ThemeSwitch';
import { useTheme } from '@/lib/theme/ThemeProvider';

export function TopBarThemeSwitch() {
  const { mode, toggleMode } = useTheme();

  return <ThemeSwitch theme={mode} onChange={toggleMode} iconOnly />;
}
