'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Check, Map, Search, MessageSquare, BrainCircuit, Waypoints, Folder, FlaskConical, Code, Presentation, LayoutGrid, Store, Settings, Activity, Boxes,
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFilesStore } from '@/stores/files';
import { useOntologyStore } from '@/stores/ontology';
import { getWorkspacePath } from './utils';
import { WorkspaceMark } from '../workspace-mark';
import { getWorkspaceSwitchPath } from '@/lib/feature-access';
import { markAppsSkipRestore, clearAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';

type SectionDef = {
  id: SidebarSection;
  icon: React.ReactNode;
  label: string;
  href: string;
  feature?: 'maps' | 'chat' | 'files' | 'agents' | 'apps' | 'marketplace' | 'search' | 'ontology' | 'graph' | 'code' | 'slides' | 'settings.workspace';
  extraHref?: string;
};

const SECTIONS: SectionDef[] = [
  { id: 'maps',     icon: <Map size={18} />,           label: 'Maps',           href: '/maps',     feature: 'maps' },
  { id: 'search',   icon: <Search size={18} />,      label: 'Search',          href: '/search',   feature: 'search' },
  { id: 'chat',     icon: <MessageSquare size={18} />, label: 'Chat',           href: '/chat',     feature: 'chat' },
  { id: 'ontology', icon: <BrainCircuit size={18} />,  label: 'Ontology',       href: '/ontology', feature: 'ontology' },
  { id: 'graph',    icon: <Waypoints size={18} />,     label: 'Knowledge Graph', href: '/graph',    feature: 'graph' },
  { id: 'files',    icon: <Folder size={18} />,        label: 'Files',          href: '/files',    feature: 'files' },
  { id: 'lab',      icon: <FlaskConical size={18} />,  label: 'Lab',            href: '/lab',         feature: 'agents' },
  { id: 'slides',   icon: <Presentation size={18} />,  label: 'Slides',         href: '/slides',   feature: 'slides' },
  { id: 'code',     icon: <Code size={18} />,          label: 'Code',           href: '/code',     feature: 'code' },
  { id: 'apps',        icon: <LayoutGrid size={18} />,    label: 'Apps',        href: '/apps',        feature: 'apps' },
  { id: 'marketplace', icon: <Store size={18} />,        label: 'Marketplace', href: '/marketplace', feature: 'marketplace' },
];

const BOTTOM_SECTIONS: SectionDef[] = [
  { id: 'settings', icon: <Settings size={18} />, label: 'Settings', href: '/settings', feature: 'settings.workspace' },
];

const ALL_SECTIONS: SectionDef[] = [...SECTIONS, ...BOTTOM_SECTIONS];

export function Sidebar() {
  const [mounted, setMounted] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const workspaceBtnRef = useRef<HTMLButtonElement>(null);
  const router = useRouter();
  const pathname = usePathname();

  const {
    workspaces,
    currentWorkspaceId,
    activePanelSection,
    setActivePanelSection,
    setCurrentWorkspace,
  } = useWorkspaceStore();

  const { fetchFiles, fetchLabFiles, setActiveSource } = useFilesStore();
  const { fetchItems: fetchOntology } = useOntologyStore();

  const canMaps = useFeature('maps');
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canAgents = useFeature('agents');
  const canApps = useFeature('apps');
  const canMarketplace = useFeature('marketplace');
  const canSearch = useFeature('search');
  const canOntology = useFeature('ontology');
  const canGraph = useFeature('graph');
  const canCode = useFeature('code');
  const canSlides = useFeature('slides');
  const canSettingsWorkspace = useFeature('settings.workspace');
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Resolve the section that owns the current URL — single source of truth
  // for the highlighted icon, the sub-panel, and the browser tab title.
  const urlSection = useMemo(() => {
    return ALL_SECTIONS.find((s) => {
      const base = getWorkspacePath(currentWorkspaceId, s.href);
      if (pathname.startsWith(base)) return true;
      if (s.extraHref) {
        const extra = getWorkspacePath(currentWorkspaceId, s.extraHref);
        if (pathname.startsWith(extra)) return true;
      }
      return false;
    }) ?? null;
  }, [pathname, currentWorkspaceId]);

  useEffect(() => {
    if (urlSection?.id === 'files' && canFiles) { fetchFiles(); fetchLabFiles(); }
    if (urlSection?.id === 'ontology' && canOntology) { fetchOntology(); }
  }, [urlSection?.id, currentWorkspaceId, canFiles, canOntology, fetchFiles, fetchLabFiles, fetchOntology]);

  // Reconcile activePanelSection with the URL whenever the URL changes
  // (incl. initial mount after rehydration). Without this, a persisted
  // activePanelSection can disagree with the page being rendered.
  const lastReconciledPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (lastReconciledPathRef.current === pathname) return;
    lastReconciledPathRef.current = pathname;
    // Admin routes (Events, Dagster) own no section panel — close it
    // so they render full-width without the secondary sidebar.
    if (!urlSection) {
      if (pathname.includes('/admin/')) setActivePanelSection(null);
      return;
    }
    setActivePanelSection(urlSection.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, urlSection]);

  const currentWorkspace = mounted ? workspaces.find((w) => w.id === currentWorkspaceId) || null : null;
  const displayWorkspaces = mounted ? workspaces : [];

  const isFeatureEnabled = (feature?: SectionDef['feature']) => {
    if (!feature) return true;
    if (feature === 'maps') return !!canMaps;
    if (feature === 'chat') return !!canChat;
    if (feature === 'files') return !!canFiles;
    if (feature === 'agents') return !!canAgents;
    if (feature === 'apps') return !!canApps;
    if (feature === 'marketplace') return !!canMarketplace;
    if (feature === 'search') return !!canSearch;
    if (feature === 'ontology') return !!canOntology;
    if (feature === 'graph') return !!canGraph;
    if (feature === 'code') return !!canCode;
    if (feature === 'slides') return !!canSlides;
    if (feature === 'settings.workspace') return !!canSettingsWorkspace;
    return true;
  };

  // Icon highlight follows the URL only. activePanelSection drives the
  // sub-panel, but the icon must always match the page being rendered.
  const isSectionActive = (section: SectionDef) => {
    const base = getWorkspacePath(currentWorkspaceId, section.href);
    if (pathname.startsWith(base)) return true;
    if (section.extraHref) {
      const extra = getWorkspacePath(currentWorkspaceId, section.extraHref);
      if (pathname.startsWith(extra)) return true;
    }
    return false;
  };

  const getDefaultPath = (sectionId: SidebarSection): string => {
    switch (sectionId) {
      case 'maps':     return getWorkspacePath(currentWorkspaceId, '/maps/presence');
      case 'search':   return getWorkspacePath(currentWorkspaceId, '/search');
      case 'chat':     return getWorkspacePath(currentWorkspaceId, '/chat');
      case 'ontology': {
        const ontologyPath =
          useOntologyStore.getState().selectedOntologyPath
          ?? '/app/libs/naas-abi-core/naas_abi_core/modules/bfo/ontologies/modules/bfo-core.ttl';
        const params = new URLSearchParams({ view: 'network', ontology: ontologyPath });
        return getWorkspacePath(currentWorkspaceId, `/ontology?${params.toString()}`);
      }
      case 'graph':    return getWorkspacePath(currentWorkspaceId, '/graph/network');
      case 'files':    return getWorkspacePath(currentWorkspaceId, '/files');
      case 'lab':      return getWorkspacePath(currentWorkspaceId, '/lab');
      case 'code':     return getWorkspacePath(currentWorkspaceId, '/code/workspaces');
      case 'slides':   return getWorkspacePath(currentWorkspaceId, '/slides');
      case 'apps':         return getWorkspacePath(currentWorkspaceId, '/apps');
      case 'marketplace':  return getWorkspacePath(currentWorkspaceId, '/marketplace');
      case 'settings':     return getWorkspacePath(currentWorkspaceId, '/settings');
    }
  };

  const handleSectionClick = (section: SectionDef) => {
    clearAppsSkipRestore();
    if (activePanelSection === section.id) {
      setActivePanelSection(null);
      return;
    }
    setActivePanelSection(section.id);
    if (section.id === 'files') setActiveSource('my-drive');
    router.push(getDefaultPath(section.id));
  };

  const openWorkspaceMenu = () => {
    if (!workspaceBtnRef.current) return;
    const rect = workspaceBtnRef.current.getBoundingClientRect();
    setDropdownPos({ top: rect.top, left: rect.right + 8 });
    setWorkspaceMenuOpen(true);
  };

  // Clicking the aside background (not a child button) toggles expanded
  const handleAsideClick = (e: React.MouseEvent<HTMLElement>) => {
    if (e.target === e.currentTarget) setExpanded((v) => !v);
  };

  return (
    <aside
      onClick={handleAsideClick}
      className={cn(
        'glass flex h-full flex-col border-r border-border/50 flex-shrink-0 transition-all duration-300',
        expanded ? 'w-48' : 'w-14'
      )}
    >
      {/* Workspace logo / switcher */}
      <div
        data-workspace-menu
        className={cn(
          'flex h-14 flex-shrink-0 items-center border-b border-border/50',
          expanded ? 'px-3 gap-3' : 'justify-center'
        )}
      >
        <button
          ref={workspaceBtnRef}
          onClick={openWorkspaceMenu}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg transition-all hover:ring-2 hover:ring-workspace-accent/50"
          style={{ backgroundColor: currentWorkspace?.theme?.primaryColor || '#22c55e' }}
          title={currentWorkspace?.name || 'NEXUS'}
        >
          <WorkspaceMark
            name={currentWorkspace?.name}
            icon={currentWorkspace?.icon}
            logoUrl={currentWorkspace?.theme?.logoUrl}
            logoEmoji={currentWorkspace?.theme?.logoEmoji}
            letterClassName="text-sm font-bold text-white"
          />
        </button>

        {expanded && (
          <span className="truncate text-sm font-medium text-foreground">
            {currentWorkspace?.name || 'NEXUS'}
          </span>
        )}
      </div>

      {/* Section icon buttons */}
      <nav
        onClick={handleAsideClick}
        className={cn(
          'flex flex-1 flex-col gap-1 py-3',
          expanded ? 'px-2' : 'items-center px-2'
        )}
      >
        {SECTIONS.filter((s) => isFeatureEnabled(s.feature)).map((section) => {
          const active = isSectionActive(section);
          return (
            <button
              key={section.id}
              onClick={() => handleSectionClick(section)}
              title={!expanded ? section.label : undefined}
              className={cn(
                'flex items-center rounded-lg transition-all',
                'hover:bg-workspace-accent-10 hover:text-workspace-accent',
                active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-muted-foreground',
                expanded ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center'
              )}
            >
              <span className="flex-shrink-0">{section.icon}</span>
              {expanded && <span className="truncate text-sm font-medium">{section.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Bottom-pinned sections (e.g. Settings) */}
      <nav
        onClick={handleAsideClick}
        className={cn(
          'flex flex-shrink-0 flex-col gap-1 border-t border-border/50 py-3',
          expanded ? 'px-2' : 'items-center px-2'
        )}
      >
        {isSuperadmin && [
          { key: 'admin-events', href: '/admin/events', label: 'Events', icon: <Activity size={18} /> },
          { key: 'admin-services', href: '/admin/services', label: 'Services', icon: <Boxes size={18} /> },
        ].map((item) => {
          const base = getWorkspacePath(currentWorkspaceId, item.href);
          const active = pathname.startsWith(base);
          return (
            <button
              key={item.key}
              onClick={() => { setActivePanelSection(null); router.push(base); }}
              title={!expanded ? item.label : undefined}
              className={cn(
                'flex items-center rounded-lg transition-all',
                'hover:bg-workspace-accent-10 hover:text-workspace-accent',
                active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-muted-foreground',
                expanded ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center'
              )}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {expanded && <span className="truncate text-sm font-medium">{item.label}</span>}
            </button>
          );
        })}
        {BOTTOM_SECTIONS.filter((s) => isFeatureEnabled(s.feature)).map((section) => {
          const active = isSectionActive(section);
          return (
            <button
              key={section.id}
              onClick={() => handleSectionClick(section)}
              title={!expanded ? section.label : undefined}
              className={cn(
                'flex items-center rounded-lg transition-all',
                'hover:bg-workspace-accent-10 hover:text-workspace-accent',
                active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-muted-foreground',
                expanded ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center'
              )}
            >
              <span className="flex-shrink-0">{section.icon}</span>
              {expanded && <span className="truncate text-sm font-medium">{section.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Workspace dropdown — portal so it escapes the glass stacking context */}
      {workspaceMenuOpen && mounted && createPortal(
        <>
          <div className="fixed inset-0 z-[199]" onClick={() => setWorkspaceMenuOpen(false)} />
          <div
            className="glass-card fixed z-[200] w-60 py-1 shadow-lg"
            style={{ top: dropdownPos.top, left: dropdownPos.left }}
          >
            <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Workspaces
            </p>
            {displayWorkspaces.map((workspace) => (
              <button
                key={workspace.id}
                onClick={() => {
                  setWorkspaceMenuOpen(false);
                  if (workspace.id === currentWorkspaceId) return;
                  markAppsSkipRestore();
                  setCurrentWorkspace(workspace.id);
                  router.push(
                    getWorkspaceSwitchPath({
                      pathname,
                      targetWorkspaceId: workspace.id,
                      role: workspace.currentUserRole,
                      workspaceFlags: workspace.featureFlags,
                    }),
                  );
                }}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                  'hover:bg-workspace-accent-10',
                  currentWorkspaceId === workspace.id && 'bg-workspace-accent-5'
                )}
              >
                <div
                  className="flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden"
                  style={{
                    backgroundColor: workspace.theme?.primaryColor || '#22c55e',
                    borderRadius: 0,
                  }}
                >
                  <WorkspaceMark
                    name={workspace.name}
                    icon={workspace.icon}
                    logoUrl={workspace.theme?.logoUrl}
                    logoEmoji={workspace.theme?.logoEmoji}
                    letterClassName="text-xs text-white"
                  />
                </div>
                <span className="flex-1 text-left font-medium">{workspace.name}</span>
                {currentWorkspaceId === workspace.id && (
                  <Check size={14} className="text-workspace-accent" />
                )}
              </button>
            ))}
          </div>
        </>,
        document.body
      )}
    </aside>
  );
}
