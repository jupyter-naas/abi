'use client';

import { useState, useEffect, useRef, type ReactNode } from 'react';
import Link from 'next/link';
import {
  PanelLeft,
  PanelRight,
  User,
  LogOut,
  HelpCircle,
  Building2,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useRegisterShellTitle } from './shell-title';

interface HeaderProps {
  title?: string;
  subtitle?: string;
  /**
   * Central / app menu bar (e.g. Slides File · View). Rendered after sidebar
   * toggles on the left, classic Office-style placement.
   */
  nav?: ReactNode;
  /** Page-level actions, rendered ahead of the global chrome on the right. */
  actions?: ReactNode;
}

export function Header({ title, subtitle, nav, actions }: HeaderProps = {}) {
  const isMobile = useIsMobile();
  // Desktop chrome does not paint the title, but it is the page's declaration
  // of where the user is, so publish it for the mobile top bar.
  useRegisterShellTitle(title, subtitle);
  const [mounted, setMounted] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { logout, user: authUser } = useAuthStore();

  const {
    sidebarCollapsed,
    toggleSidebar,
    contextPanelOpen,
    toggleContextPanel,
    currentWorkspaceId,
    activePanelSection,
    setActivePanelSection,
    lastActivePanelSection,
  } = useWorkspaceStore();

  // Use authenticated user from auth store (not the hardcoded workspace store user)
  const user = authUser;

  const canOrganizationSettings = useFeature('settings.organization');

  // Helper to generate workspace-scoped URLs
  const getWorkspacePath = (path: string) =>
    currentWorkspaceId ? `/workspace/${currentWorkspaceId}${path}` : path;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Use defaults on server to prevent hydration mismatch
  const sidebarOpen = mounted ? !sidebarCollapsed : true;
  const panelOpen = mounted ? contextPanelOpen : false;
  const displayUser = mounted ? user : null;

  // Mobile shell owns chrome (back header + bottom nav). Desktop Header
  // (sidebar toggle, AI pane) is dead weight there. Branch + API live in
  // PlatformStatusFooter (shell), not the navbar.
  if (isMobile) return null;

  return (
    <header className="glass-nav relative z-[200] flex h-14 items-center justify-between border-b border-border/50 pl-2 pr-4">
      {/* Left side */}
      <div className="flex items-center gap-1">
        {!sidebarOpen && (
          <button
            onClick={toggleSidebar}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md transition-all',
              'hover:bg-muted hover:text-foreground text-muted-foreground'
            )}
            title="Expand sidebar"
          >
            <PanelLeft size={16} />
          </button>
        )}

        {/* Section panel toggle — visible whenever a panel section has been opened */}
        {mounted && lastActivePanelSection && (
          <button
            onClick={() => setActivePanelSection(activePanelSection ? null : lastActivePanelSection)}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md transition-all',
              'hover:bg-muted hover:text-foreground',
              activePanelSection ? 'text-foreground bg-muted' : 'text-muted-foreground'
            )}
            title={activePanelSection ? 'Close panel' : 'Open panel'}
          >
            <PanelLeft size={16} />
          </button>
        )}

        {nav ? <div className="ml-1 flex min-w-0 items-center">{nav}</div> : null}
      </div>

      {/* Right side: page actions + Abi + user. Branch/API live in PlatformStatusFooter. */}
      <div className="flex items-center gap-1">
        {actions}

        {/* Right chat pane toggle — icon-only, mirrors left PanelLeft controls */}
        <button
          type="button"
          onClick={toggleContextPanel}
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-md transition-all',
            'hover:bg-muted hover:text-foreground',
            panelOpen ? 'bg-muted text-foreground' : 'text-muted-foreground'
          )}
          title="Toggle Abi chat pane (⌘K)"
          aria-label="Toggle Abi chat pane"
          aria-pressed={panelOpen}
        >
          <PanelRight size={16} />
        </button>

        {/* User avatar with dropdown */}
        <div ref={userMenuRef} className="relative ml-1">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full overflow-hidden transition-opacity',
              'hover:opacity-90',
              displayUser?.avatar ? 'bg-transparent' : 'bg-primary text-primary-foreground'
            )}
          >
            {displayUser?.avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={displayUser.avatar}
                alt={displayUser.name || 'User'}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-xs font-medium">{displayUser?.name?.charAt(0) || 'U'}</span>
            )}
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full z-[300] mt-2 min-w-56 w-64 rounded-lg border bg-card shadow-lg p-2">
              {/* User info */}
              <div className="border-b border-border/50 px-4 py-3">
                <p className="truncate font-medium" title={displayUser?.name || 'User'}>
                  {displayUser?.name || 'User'}
                </p>
                <p className="min-w-0 truncate text-xs text-muted-foreground" title={displayUser?.email || ''}>
                  {displayUser?.email || ''}
                </p>
              </div>

              {/* Menu items */}
              <div className="py-2">
                <Link
                  href="/account/profile"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <User size={16} className="shrink-0 text-muted-foreground" />
                  Account Settings
                </Link>
                {canOrganizationSettings && (
                  <Link
                    href="/organizations"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                  >
                    <Building2 size={16} className="shrink-0 text-muted-foreground" />
                    Organization Settings
                  </Link>
                )}
                <Link
                  href={getWorkspacePath('/help')}
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-3 rounded-md px-4 py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <HelpCircle size={16} className="shrink-0 text-muted-foreground" />
                  Help
                </Link>
              </div>

              {/* Logout */}
              <div className="border-t border-border/50 py-2">
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    logout();
                    router.push('/auth/login');
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-4 py-2.5 text-sm text-destructive transition-colors hover:bg-destructive/10"
                >
                  <LogOut size={16} className="shrink-0" />
                  Log Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
