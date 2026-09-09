'use client';

import { useEffect, useState } from 'react';
import { PanelLeft, PanelRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, isTransientPanelSection } from '@/stores/workspace';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { QuickOpen } from './quick-open';
import { useTopNavContent } from './topnav-content';

/**
 * The one persistent topnav bar. Mounted once by WorkspaceLayout above main
 * content and the AI chat pane, so the pane opens below it instead of beside
 * a per-page-scoped header. Content (app-menu row, page actions) comes from
 * whichever page last called `<Header>`; mobile owns its own chrome via
 * MobileTopBar instead.
 */
export function TopNav() {
  const isMobile = useIsMobile();
  const { nav, actions } = useTopNavContent();
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
