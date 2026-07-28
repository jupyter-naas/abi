'use client';

import { useRouter } from 'next/navigation';

import type { UserConfig } from '@/lib/types';
import { useTheme } from '@/lib/theme/ThemeProvider';
import { BackToPerimetersLink } from '@/components/layout/BackToPerimetersLink';
import { TopBarTitle } from '@/components/layout/TopBarTitle';
import { Logo } from '@/components/brand/Logo';
import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

type ThemePageShellProps = {
  user: UserConfig;
  children: React.ReactNode;
};

export function ThemePageShell({ user, children }: ThemePageShellProps) {
  const router = useRouter();
  const { mode: theme, toggleMode: toggleTheme } = useTheme();

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/login');
    router.refresh();
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="topbar-chrome border-b border-[var(--border)]">
        <div className="relative flex md:hidden items-center justify-center px-4 py-4">
          <div className="absolute left-4 top-1/2 -translate-y-1/2">
            <Logo size={28} />
          </div>
          <TopBarTitle className="max-w-[min(100%,14rem)] px-16">
            Thème & couleurs
          </TopBarTitle>
          <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
            <BackToPerimetersLink />
            <ThemeToggle theme={theme} onPress={toggleTheme} />
          </div>
        </div>

        <div className="hidden md:grid grid-cols-[1fr_minmax(0,32rem)_1fr] items-center gap-4 px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <Logo size={28} />
          </div>
          <TopBarTitle>Thème & couleurs</TopBarTitle>
          <div className="relative z-10 flex justify-end items-center gap-2">
            <BackToPerimetersLink />
            <ThemeToggle theme={theme} onPress={toggleTheme} />
            <Button variant="ghost" onPress={handleLogout} className="!w-auto">
              Déconnexion
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto px-4 py-6 sm:px-6 md:px-8 md:py-8 bg-[var(--bg)]">
        <p className="mb-6 text-sm text-[var(--text-muted)]">{user.name}</p>
        {children}
      </main>

      <footer className="border-t border-[var(--border)] bg-[var(--surface)] p-4 sm:hidden">
        <Button variant="ghost" onPress={handleLogout}>
          Déconnexion
        </Button>
      </footer>
    </div>
  );
}
