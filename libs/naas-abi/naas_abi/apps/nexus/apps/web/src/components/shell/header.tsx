'use client';

import { useState, useEffect, type ReactNode } from 'react';
import {
  PanelLeft,
  PanelRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, isTransientPanelSection } from '@/stores/workspace';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { QuickOpen } from './quick-open';
import { useRegisterShellTitle } from './shell-title';

interface HeaderProps {
  title?: string;
  subtitle?: string;
  /**
   * App menu (e.g. Slides File / View). Own row under the workspace chrome
   * so it never sits on the centered search field.
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

  const {
    sidebarCollapsed,
    toggleSidebar,
    contextPanelOpen,
    toggleContextPanel,
    activePanelSection,
    setActivePanelSection,
    lastActivePanelSection,
  } = useWorkspaceStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Use defaults on server to prevent hydration mismatch
  const sidebarOpen = mounted ? !sidebarCollapsed : true;
  const panelOpen = mounted ? contextPanelOpen : false;
  const sectionToToggle =
    lastActivePanelSection && !isTransientPanelSection(lastActivePanelSection)
      ? lastActivePanelSection
      : 'chat';

  // Mobile shell owns chrome (back header + bottom nav). Desktop Header
  // (sidebar toggle, AI pane) is dead weight there. Branch + API live in
  // PlatformStatusFooter (shell), not the navbar. Account menu lives on the
  // dock (desktop) and the mobile top bar.
  if (isMobile) return null;

  return (
    <header className="glass-nav relative z-[200] shrink-0 border-b border-border/50">
      <div className="relative flex h-14 items-center pl-2 pr-4">
        <div className="relative z-10 flex min-w-0 items-center gap-1">
          {!sidebarOpen && (
            <button
              onClick={toggleSidebar}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md transition-all',
                'hover:bg-muted hover:text-foreground text-muted-foreground'
              )}
              title="Show dock"
            >
              <PanelLeft size={16} />
            </button>
          )}

          {mounted && (
            <button
              type="button"
              onClick={() => setActivePanelSection(activePanelSection ? null : sectionToToggle)}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md transition-all',
                'hover:bg-muted hover:text-foreground',
                activePanelSection ? 'text-foreground bg-muted' : 'text-muted-foreground'
              )}
              title={activePanelSection ? 'Close panel' : 'Open panel'}
              aria-label={activePanelSection ? 'Close panel' : 'Open panel'}
              aria-pressed={Boolean(activePanelSection)}
            >
              <PanelLeft size={16} />
            </button>
          )}
        </div>

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-8">
          <div className="pointer-events-auto w-full max-w-[32rem]">
            <QuickOpen />
          </div>
        </div>

        <div className="relative z-10 ml-auto flex items-center gap-1">
          {actions}

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
        </div>
      </div>

      {nav ? (
        <div
          className="flex h-9 min-w-0 items-center border-t border-border/50 bg-background/80 px-3"
          data-testid="app-menu-bar"
        >
          {nav}
        </div>
      ) : null}
    </header>
  );
}
