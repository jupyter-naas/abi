'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { PanelLeft, PanelRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, isTransientPanelSection } from '@/stores/workspace';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { TOPNAV_HEIGHT } from '@/lib/shell-columns';
import { QuickOpen } from './quick-open';
import { useTopNavContent } from './topnav-content';
import { SECTION_HOME_HREF, SECTION_LABELS } from './sidebar/section-labels';
import { getWorkspacePath } from './sidebar/utils';

/**
 * The one persistent topnav bar. Mounted once by WorkspaceLayout above the
 * feature column, main content and the AI chat pane — pushed right of the
 * dock, which owns the workspace mark and keeps its own full-height column.
 * Content specific to the current page (app-menu row, page actions) comes
 * from whichever page last called `<Header>`; mobile owns its own chrome
 * via MobileTopBar instead.
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
    sectionPanelWidth,
    currentWorkspaceId,
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

  const sectionTitleOpen = mounted && activePanelSection !== null;
  const panelTitle = activePanelSection ? SECTION_LABELS[activePanelSection] : '';
  const panelHref =
    activePanelSection && SECTION_HOME_HREF[activePanelSection]
      ? getWorkspacePath(currentWorkspaceId, SECTION_HOME_HREF[activePanelSection])
      : null;

  if (isMobile) return null;

  return (
    <header className="glass-nav relative z-[200] shrink-0 border-b border-border/50">
      <div className="relative flex items-stretch" style={{ height: TOPNAV_HEIGHT }}>
        {sectionTitleOpen && (
          <div
            className="flex h-full shrink-0 items-center pl-4 pr-3"
            style={{ minWidth: sectionPanelWidth }}
            data-testid="app-menu-bar"
          >
            {nav ? (
              nav
            ) : panelHref ? (
              <Link
                href={panelHref}
                data-testid="section-panel-title"
                className="truncate text-sm font-semibold hover:text-workspace-accent"
              >
                {panelTitle}
              </Link>
            ) : (
              <span className="truncate text-sm font-semibold">{panelTitle}</span>
            )}
          </div>
        )}

        <div className="relative z-10 flex min-w-0 items-center gap-1 pl-2 pr-2">
          {!sidebarOpen && (
            <button
              onClick={toggleSidebar}
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-md transition-all',
                'hover:bg-muted hover:text-foreground text-muted-foreground'
              )}
              title="Show dock"
            >
              <PanelLeft size={14} />
            </button>
          )}

          {mounted && (
            <button
              type="button"
              onClick={() => setActivePanelSection(activePanelSection ? null : sectionToToggle)}
              className={cn(
                'flex h-7 w-7 items-center justify-center rounded-md transition-all',
                'hover:bg-muted hover:text-foreground',
                activePanelSection ? 'text-foreground' : 'text-muted-foreground'
              )}
              title={activePanelSection ? 'Close panel' : 'Open panel'}
              aria-label={activePanelSection ? 'Close panel' : 'Open panel'}
              aria-pressed={Boolean(activePanelSection)}
            >
              <PanelLeft size={14} />
            </button>
          )}
        </div>

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-8">
          <div className="pointer-events-auto w-full max-w-[32rem]">
            <QuickOpen />
          </div>
        </div>

        <div className="relative z-10 ml-auto flex items-center gap-1 pr-4">
          {actions}

          <button
            type="button"
            onClick={toggleContextPanel}
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded-md transition-all',
              'hover:bg-muted hover:text-foreground',
              panelOpen ? 'text-foreground' : 'text-muted-foreground'
            )}
            title="Toggle Abi chat pane (⌘K)"
            aria-label="Toggle Abi chat pane"
            aria-pressed={panelOpen}
          >
            <PanelRight size={14} />
          </button>
        </div>
      </div>
    </header>
  );
}
