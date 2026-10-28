'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTheme } from 'next-themes';
import dynamic from 'next/dynamic';
import { Sidebar } from './sidebar';
import { SectionPanel } from './sidebar/section-panel';
import { TopNav } from './topnav';
import { PlatformStatusFooter } from './platform-status-footer';
import { MobileBottomNav } from './mobile/mobile-bottom-nav';
import { MobileMoreSheet } from './mobile/mobile-more-sheet';
import { MobileTopBar } from './mobile/mobile-top-bar';
import { ChatExportButton } from '@/components/chat/chat-export-button';
import {
  isMobileChatThreadOpen,
  parseChatRoute,
  resolveMobileThreadConversationId,
} from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { parseFilesRoute } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { parseMapsRoute } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { parseDatasetsRoute } from '@/app/workspace/[workspaceId]/datasets/lib/datasets-route';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { PresenceIndicator } from '@/components/presence-indicator';
import { getWorkspacePath } from './sidebar/utils';
import { pathNeedsAgentCatalog } from '@/lib/feature-access';
import { rememberWorkspacePath } from '@/lib/workspace-return-path';
import { loadOrgBranding, resolveWorkspaceOrgId } from '@/lib/org-branding';
import { OfficeCreateOverlay } from '@/components/office/office-create-overlay';

const AIPane = dynamic(() => import('./ai-pane').then((m) => m.AIPane), { ssr: false });
const ChatSection = dynamic(
  () => import('@/app/workspace/[workspaceId]/chat/components/chat-section').then((m) => m.ChatSection),
  { ssr: false },
);
const ChatInterface = dynamic(
  () => import('@/components/chat/chat-interface').then((m) => m.ChatInterface),
  { ssr: false },
);
const FilesSection = dynamic(() => import('./sidebar/files-section').then((m) => m.FilesSection), {
  ssr: false,
});
const MapsSection = dynamic(() => import('./sidebar/maps-section').then((m) => m.MapsSection), {
  ssr: false,
});
const DatasetsSection = dynamic(
  () => import('./sidebar/datasets-section').then((m) => m.DatasetsSection),
  { ssr: false },
);

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

// Convert hex to HSL for Tailwind CSS variables
function hexToHSL(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return '160 84% 45%'; // fallback to default primary
  
  let r = parseInt(result[1], 16) / 255;
  let g = parseInt(result[2], 16) / 255;
  let b = parseInt(result[3], 16) / 255;
  
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

export function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  // Subscribe to reactive state to trigger re-render on workspace change
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const toggleContextPanel = useWorkspaceStore((state) => state.toggleContextPanel);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const mobilePendingChatSlug = useWorkspaceStore((state) => state.mobilePendingChatSlug);
  const setMobilePendingChatSlug = useWorkspaceStore((state) => state.setMobilePendingChatSlug);
  const contextPanelOpen = useWorkspaceStore((state) => state.contextPanelOpen);
  const activePanelSection = useWorkspaceStore((state) => state.activePanelSection);
  const { setTheme } = useTheme();
  const [orgBorderRadius, setOrgBorderRadius] = useState('0');
  const [moreOpen, setMoreOpen] = useState(false);
  const isMobile = useIsMobile();
  const pathname = usePathname();
  const router = useRouter();

  // Fetch workspaces on mount
  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  // Org branding (border radius AND theme). The org id comes from the loaded
  // workspace record; branding is cached per org, so switching between
  // workspaces of one org costs no request (see lib/org-branding).
  const workspaceLoaded = workspaces.some((w) => w.id === currentWorkspaceId);
  const workspaceOrgId = workspaces.find((w) => w.id === currentWorkspaceId)?.organizationId;
  const [brandingVersion, setBrandingVersion] = useState(0);
  useEffect(() => {
    const handleBrandingUpdate = () => setBrandingVersion((v) => v + 1);
    window.addEventListener('org-branding-updated', handleBrandingUpdate);
    return () => window.removeEventListener('org-branding-updated', handleBrandingUpdate);
  }, []);

  useEffect(() => {
    if (!currentWorkspaceId || !workspaceLoaded) return;
    // A slow reply for the previous workspace/org must not overwrite this one.
    let cancelled = false;
    const applyOrgBranding = async () => {
      const orgId = await resolveWorkspaceOrgId(currentWorkspaceId, workspaceOrgId);
      const branding = orgId ? await loadOrgBranding(orgId) : null;
      if (cancelled) return;
      setOrgBorderRadius(branding?.borderRadius ?? '0');
      // A failed lookup leaves the current theme alone.
      if (!branding) return;
      // Apply org theme ONLY if user hasn't explicitly overridden it
      const hasUserOverride = localStorage.getItem('nexus-theme-user-override') === 'true';
      // Default to light when org has no theme
      if (!hasUserOverride) setTheme(branding.defaultTheme ?? 'light');
    };
    applyOrgBranding();
    return () => {
      cancelled = true;
    };
    // setTheme is omitted: it caused infinite loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId, workspaceLoaded, workspaceOrgId, brandingVersion]);

  // Listen for real-time theme changes from branding page
  useEffect(() => {
    const handleThemeChange = (event: CustomEvent) => {
      const newTheme = event.detail;
      console.log('[WorkspaceLayout] Theme change event:', newTheme);
      
      // Only apply if user hasn't overridden
      const hasUserOverride = localStorage.getItem('nexus-theme-user-override') === 'true';
      if (!hasUserOverride && newTheme && (newTheme === 'light' || newTheme === 'dark' || newTheme === 'system')) {
        setTheme(newTheme);
      }
    };

    window.addEventListener('org-theme-changed', handleThemeChange as EventListener);
    return () => window.removeEventListener('org-theme-changed', handleThemeChange as EventListener);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Agents/skills belong to chat, agent settings, and the open AI pane.
  // Fetching them on every workspace switch (including Apps) POSTed
  // /agents/sync and starved GET /api/apps.
  // Keyed on the boolean, not the pathname: re-fetching (and re-persisting)
  // the agent catalog on every section switch while the pane is open was a
  // fixed cost on each dock click.
  const needsAgents = Boolean(
    currentWorkspaceId && (contextPanelOpen || pathNeedsAgentCatalog(pathname)),
  );
  useEffect(() => {
    if (!needsAgents || !currentWorkspaceId) return;
    const loadAgents = async () => {
      const { ensureAgentsSynced, useAgentsStore } = await import('@/stores/agents');
      // Chat and agent settings need a reconciled roster; Apps only need GET.
      if (contextPanelOpen || pathNeedsAgentCatalog(pathname)) {
        await ensureAgentsSynced(currentWorkspaceId);
      }
      await useAgentsStore.getState().fetchAgents(currentWorkspaceId);
    };
    const loadSkills = async () => {
      const { useSkillsStore } = await import('@/stores/skills');
      await useSkillsStore.getState().fetchSkills(currentWorkspaceId);
    };
    loadAgents();
    loadSkills();
  }, [currentWorkspaceId, contextPanelOpen, needsAgents, pathname]);

  // Keyboard shortcut: Cmd+K to toggle the side chat pane (desktop only).
  // Capture phase so Monaco / editors do not swallow ⌘K as a chord starter.
  useEffect(() => {
    if (isMobile) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        e.stopPropagation();
        toggleContextPanel();
      }
    };
    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [toggleContextPanel, isMobile]);

  // Find current workspace from state
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  
  // Get theme colors with fallbacks
  const primaryColor = currentWorkspace?.theme?.primaryColor || '#22c55e';
  const accentColor = currentWorkspace?.theme?.accentColor || primaryColor;
  
  // Apply theme to document root for Tailwind CSS variables
  useEffect(() => {
    if (primaryColor && accentColor) {
      const root = document.documentElement;
      const primaryHSL = hexToHSL(primaryColor);
      const accentHSL = hexToHSL(accentColor);
      
      // Override Tailwind's --primary and --accent CSS variables
      root.style.setProperty('--primary', primaryHSL);
      root.style.setProperty('--accent', accentHSL);
      
      // Keep legacy workspace variables for compatibility
      root.style.setProperty('--workspace-primary', primaryColor);
      root.style.setProperty('--workspace-accent', accentColor);
      root.style.setProperty('--workspace-primary-hsl', primaryHSL);
      root.style.setProperty('--workspace-accent-hsl', accentHSL);
    }
  }, [primaryColor, accentColor]);
  
  // Also on the root element, not just the shell div: menus and sheets render
  // through portals into document.body, outside any inline style we set here.
  useEffect(() => {
    document.documentElement.style.setProperty('--org-border-radius', `${orgBorderRadius}px`);
  }, [orgBorderRadius]);

  // Create dynamic CSS variables for org branding
  const themeStyles = {
    '--org-border-radius': `${orgBorderRadius}px`,
  } as React.CSSProperties;

  // The URL owns which chat view is showing: /chat is the list, /chat/{id} and
  // /chat/new are threads. mobilePendingChatSlug lets the shell flip to the
  // thread immediately on tap before router.push updates the pathname.
  const chatRoute = parseChatRoute(pathname);
  const { isChatRoute, isThread } = chatRoute;
  const { isFilesRoute, isBrowse: isFilesBrowse } = parseFilesRoute(pathname);
  const searchParams = useSearchParams();
  // Settings pages (Organization, Platform) send the user back to this page.
  const searchKey = searchParams?.toString() ?? '';
  useEffect(() => {
    if (pathname) rememberWorkspacePath(searchKey ? `${pathname}?${searchKey}` : pathname);
  }, [pathname, searchKey]);
  const mapsRoute = parseMapsRoute(pathname, searchParams);
  const { isMapsRoute, isMapView: isMapsDataset } = mapsRoute;
  const { isDatasetsRoute, isTable: isDatasetsTable } = parseDatasetsRoute(pathname);
  const showMobileChatThread = isMobile && isMobileChatThreadOpen(chatRoute, mobilePendingChatSlug);
  const showMobileChatList = isMobile && isChatRoute && !showMobileChatThread;
  const mobileThreadConversationId = resolveMobileThreadConversationId(
    chatRoute,
    mobilePendingChatSlug,
  );
  const showMobileFilesList = isMobile && isFilesRoute && !isFilesBrowse;
  const showMobileFilesDetail = isMobile && isFilesRoute && isFilesBrowse;
  const showMobileMapsList = isMobile && isMapsRoute && !isMapsDataset;
  const showMobileMapsDetail = isMobile && isMapsRoute && isMapsDataset;
  const showMobileDatasetsList = isMobile && isDatasetsRoute && !isDatasetsTable;
  const showMobileDatasetsDetail = isMobile && isDatasetsRoute && isDatasetsTable;
  const showMobileDetail = showMobileChatThread || showMobileFilesDetail || showMobileMapsDetail || showMobileDatasetsDetail;

  useEffect(() => {
    if (mobilePendingChatSlug && isThread) {
      setMobilePendingChatSlug(null);
    }
  }, [mobilePendingChatSlug, isThread, setMobilePendingChatSlug]);

  const handleFilesListBack = () => {
    router.replace(getWorkspacePath(currentWorkspaceId, '/files'));
  };

  const handleMapsListBack = () => {
    router.replace(getWorkspacePath(currentWorkspaceId, '/maps'));
  };

  const handleDatasetsListBack = () => {
    router.replace(getWorkspacePath(currentWorkspaceId, '/datasets'));
  };

  // Detail views are immersive: dismiss More if it was open.
  useEffect(() => {
    if (showMobileDetail) setMoreOpen(false);
  }, [showMobileDetail]);

  if (isMobile) {
    return (
      <div
        className="flex h-[100dvh] w-screen flex-col overflow-hidden bg-background"
        style={themeStyles}
        data-org-branded="true"
        data-mobile-shell="true"
      >
        <MobileTopBar
          variant={showMobileDetail ? 'detail' : 'top'}
          // List screens are shell-owned, so no page Header is mounted to name them.
          title={
            showMobileChatList ? 'Chat'
              : showMobileFilesList ? 'Files'
                : showMobileMapsList ? 'Maps'
                  : showMobileDatasetsList ? 'Datasets'
                    : undefined
          }
          // The page passes its actions to the desktop Header, but mobile chrome
          // is shell-owned, so the route decides what the bar carries.
          actions={showMobileChatThread ? <ChatExportButton /> : undefined}
          onDetailBack={
            showMobileFilesDetail
              ? handleFilesListBack
              : showMobileMapsDetail
                ? handleMapsListBack
                : showMobileDatasetsDetail
                  ? handleDatasetsListBack
                  : undefined
          }
          detailBackLabel={
            showMobileFilesDetail
              ? 'Back to files'
              : showMobileMapsDetail
                ? 'Back to maps'
                : showMobileDatasetsDetail
                  ? 'Back to datasets'
                  : undefined
          }
        />
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {currentWorkspaceId && <PresenceIndicator workspaceId={currentWorkspaceId} />}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {showMobileChatList ? (
              <nav className="min-h-0 flex-1 overflow-y-auto p-2">
                <ChatSection collapsed={false} detailOnly />
              </nav>
            ) : showMobileFilesList ? (
              <nav className="min-h-0 flex-1 overflow-y-auto p-2">
                <FilesSection collapsed={false} detailOnly />
              </nav>
            ) : showMobileMapsList ? (
              <nav className="min-h-0 flex-1 overflow-y-auto p-2">
                <MapsSection collapsed={false} detailOnly />
              </nav>
            ) : showMobileDatasetsList ? (
              <nav className="min-h-0 flex-1 overflow-y-auto p-2">
                <DatasetsSection collapsed={false} detailOnly />
              </nav>
            ) : showMobileChatThread ? (
              // Flex column so ChatInterface flex-1/h-full fills the shell and the
              // composer pins to the bottom (empty + non-empty). A plain block
              // wrapper leaves the chat column content-sized and mid-screen.
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <ChatInterface initialConversationId={mobileThreadConversationId} />
              </div>
            ) : (
              <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
                {children}
                <OfficeCreateOverlay />
              </div>
            )}
            <PlatformStatusFooter />
          </div>
        </main>

        {/* Teams-style: bottom nav on list tabs only. Detail views own the screen. */}
        {!showMobileDetail && (
          <>
            <MobileBottomNav
              moreOpen={moreOpen}
              onMoreToggle={() => setMoreOpen((v) => !v)}
            />
            <MobileMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
          </>
        )}
      </div>
    );
  }

  return (
    <div
      className="flex h-screen w-screen overflow-hidden bg-background"
      style={themeStyles}
      data-org-branded="true"
    >
      {/* Workspaces list: left of the dock when the mark is open. Other
          feature columns stay to the right of the dock, below TopNav. */}
      {activePanelSection === 'workspaces' ? <SectionPanel /> : null}

      {/* Dock: workspace mark, nav, profile — a full top-to-bottom column of
          its own. Width matches the feature column by default and is resizable. */}
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Topnav: active section title / app menu, page header, chat pane
            toggle. Spans the region right of the dock — pushed by it — so
            the feature column, main content and AI pane share one header
            instead of each painting their own. */}
        <TopNav />

        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* Feature column: Chat, Files, Events, ... */}
          {activePanelSection === 'workspaces' ? null : <SectionPanel />}

          {/* Main content + the AI chat pane, opening below TopNav instead of
              beside a per-page-scoped header. */}
          <main className="flex flex-1 flex-col overflow-hidden">
            {currentWorkspaceId && <PresenceIndicator workspaceId={currentWorkspaceId} />}
            <div className="relative min-h-0 flex-1 overflow-hidden">
              {children}
              <OfficeCreateOverlay />
            </div>
          </main>

          {contextPanelOpen && <AIPane />}
        </div>

        {/* Footer: Repo / Branch / Code workspace. Same region as TopNav, pushed by the dock. */}
        <PlatformStatusFooter />
      </div>
    </div>
  );
}
