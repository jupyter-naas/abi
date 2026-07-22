'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { useTheme } from '@/lib/theme/ThemeProvider';
import { Logo } from '@/components/brand/Logo';
import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { TopBarTitle } from '@/components/layout/TopBarTitle';

type GalleryShellProps = {
  appName: string;
  showAdminLink?: boolean;
  children: React.ReactNode;
};

export function GalleryShell({
  appName,
  showAdminLink = false,
  children,
}: GalleryShellProps) {
  const router = useRouter();
  const { mode: theme, toggleMode: toggleTheme } = useTheme();

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/login');
    router.refresh();
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="topbar-chrome border-b border-[var(--border)]">
        <div className="mx-auto grid w-full max-w-6xl grid-cols-[1fr_minmax(0,32rem)_1fr] items-center gap-4 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <Logo size={28} />
          </div>
          <TopBarTitle>{appName}</TopBarTitle>
          <div className="flex items-center justify-end gap-2 shrink-0">
            <ThemeToggle theme={theme} onPress={toggleTheme} />
            {showAdminLink ? (
              <Link
                href="/admin"
                className="inline-flex items-center text-xs font-medium text-[var(--text-muted)] outline-none hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-secondary"
              >
                Administration
              </Link>
            ) : null}
            <Button variant="ghost" onPress={handleLogout} className="!w-auto">
              Déconnexion
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </div>
  );
}
