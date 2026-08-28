'use client';

import { useState, useEffect, type ReactNode } from 'react';
import {
  PanelLeft,
  PanelRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, isTransientPanelSection } from '@/stores/workspace';
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

  // Mobile shell owns chrome (back header + bottom nav). Desktop Header
  // (sidebar toggle, AI pane) is dead weight there. Branch + API live in
  // PlatformStatusFooter (shell), not the navbar. Account menu lives on the
  // dock (desktop) and the mobile top bar.
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
            title="Show dock"
          >
            <PanelLeft size={16} />
          </button>
        )}

        {/* Section panel toggle: visible whenever a panel section has been opened */}
        {mounted && lastActivePanelSection && !isTransientPanelSection(lastActivePanelSection) && (
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

      {/* Right side: page actions + Abi pane. Account menu is on the dock. */}
      <div className="flex items-center gap-1">
        {actions}

        {/* Right chat pane toggle: icon-only, mirrors left PanelLeft controls */}
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
    </header>
  );
}
