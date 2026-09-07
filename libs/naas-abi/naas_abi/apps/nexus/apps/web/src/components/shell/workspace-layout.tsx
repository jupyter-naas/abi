'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { Sidebar } from './sidebar';
import { SectionPanel } from './sidebar/section-panel';
import { ChatSection } from '@/app/workspace/[workspaceId]/chat/components/chat-section';
import { AIPane } from './ai-pane';
import { PlatformStatusFooter } from './platform-status-footer';
import { MobileBottomNav } from './mobile/mobile-bottom-nav';
import { MobileMoreSheet } from './mobile/mobile-more-sheet';
import { MobileTopBar } from './mobile/mobile-top-bar';
import { ChatExportButton } from '@/components/chat/chat-export-button';
import { ChatInterface } from '@/components/chat/chat-interface';
import {
  isMobileChatThreadOpen,
  parseChatRoute,
  resolveMobileThreadConversationId,
} from '@/app/workspace/[workspaceId]/chat/lib/chat-route';
import { parseFilesRoute } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { parseMapsRoute } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { parseDatasetsRoute } from '@/app/workspace/[workspaceId]/datasets/lib/datasets-route';
import { FilesSection } from './sidebar/files-section';
import { MapsSection } from './sidebar/maps-section';
import { DatasetsSection } from './sidebar/datasets-section';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { PresenceIndicator } from '@/components/presence-indicator';
import { getWorkspacePath } from './sidebar/utils';
import { pathNeedsAgentCatalog } from '@/lib/feature-access';

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

  // Fetch org branding to get border radius AND theme
  useEffect(() => {
    const fetchOrgBranding = async () => {
      const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
      if (!currentWorkspace) return;

      // Check if user has explicitly overridden theme
      const hasUserOverride = localStorage.getItem('nexus-theme-user-override') === 'true';

      // Fetch workspace details to get organization_id
      try {
        const { authFetch } = await import('@/stores/auth');
        const wsResponse = await authFetch(`/api/workspaces/${currentWorkspaceId}`);
        if (wsResponse.ok) {
          const wsData = await wsResponse.json();
          if (wsData.organization_id) {
            // Fetch org branding
            const orgResponse = await authFetch(`/api/organizations/${wsData.organization_id}`);
            if (orgResponse.ok) {
              const orgData = await orgResponse.json();
              // Handle border radius - allow 0, only fallback if undefined/null
              const radius = orgData.loginBorderRadius ?? orgData.login_border_radius ?? '0';
              console.log('[WorkspaceLayout] Org border radius:', radius, 'from org:', wsData.organization_id);
              setOrgBorderRadius(radius);

              // Apply org theme ONLY if user hasn't explicitly overridden it
              if (!hasUserOverride) {
                const orgTheme = orgData.defaultTheme || orgData.default_theme;
                if (orgTheme && (orgTheme === 'light' || orgTheme === 'dark' || orgTheme === 'system')) {
                  console.log('[WorkspaceLayout] Applying org theme (no user override):', orgTheme);
                  setTheme(orgTheme);
                } else {
                  console.log('[WorkspaceLayout] No org theme set, defaulting to light');
                  // Default to light when org has no theme
                  setTheme('light');
                }
              } else {
                console.log('[WorkspaceLayout] User has overridden theme, skipping org theme');
              }
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch org branding:', error);
      }
    };

    if (currentWorkspaceId) {
      fetchOrgBranding();
    }

    // Listen for real-time theme changes from branding page
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
    // REMOVED workspaces and setTheme - they cause infinite loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId]);

  // Agents/skills belong to chat, lab, agent settings, and the open AI pane.
  // Fetching them on every workspace switch (including Apps) POSTed
  // /agents/sync and starved GET /api/apps.
  useEffect(() => {
    const needsAgents = Boolean(
      currentWorkspaceId && (contextPanelOpen || pathNeedsAgentCatalog(pathname)),
    );
    if (!needsAgents || !currentWorkspaceId) return;
    const loadAgents = async () => {
      const { useAgentsStore } = await import('@/stores/agents');
      await useAgentsStore.getState().fetchAgents(currentWorkspaceId);
    };
    const loadSkills = async () => {
      const { useSkillsStore } = await import('@/stores/skills');
      await useSkillsStore.getState().fetchSkills(currentWorkspaceId);
    };
    loadAgents();
    loadSkills();
  }, [currentWorkspaceId, contextPanelOpen, pathname]);

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
  const { isMapsRoute, isDataset: isMapsDataset } = parseMapsRoute(pathname);
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
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
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
      {/* Dock: workspace mark, nav, profile. Width matches the feature column by default and is resizable. */}
      <Sidebar />

      {/* Feature column: Chat, Files, Workspaces, ... */}
      <SectionPanel />

      {/* Main content + platform status footer (User / Business workspace / Repo / Branch / Code workspace) */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {currentWorkspaceId && <PresenceIndicator workspaceId={currentWorkspaceId} />}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
          <PlatformStatusFooter />
        </div>
      </main>

      {/* Right AI pane */}
      <AIPane />
    </div>
  );
}
