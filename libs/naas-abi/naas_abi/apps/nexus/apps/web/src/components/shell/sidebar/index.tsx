'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Check, Search, MessageSquare, BrainCircuit, Waypoints, Folder, FlaskConical, LayoutGrid, Store, Settings, Activity,
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFilesStore } from '@/stores/files';
import { useOntologyStore } from '@/stores/ontology';
import { getWorkspacePath } from './utils';

type SectionDef = {
  id: SidebarSection;
  icon: React.ReactNode;
  label: string;
  href: string;
  feature?: 'chat' | 'files' | 'agents' | 'apps' | 'marketplace' | 'search' | 'ontology' | 'graph' | 'settings.workspace';
  extraHref?: string;
};

const SECTIONS: SectionDef[] = [
  { id: 'search',   icon: <Search size={18} />,      label: 'Search',          href: '/search',   feature: 'search' },
  { id: 'chat',     icon: <MessageSquare size={18} />, label: 'Chat',           href: '/chat',     feature: 'chat' },
  { id: 'ontology', icon: <BrainCircuit size={18} />,  label: 'Ontology',       href: '/ontology', feature: 'ontology' },
  { id: 'graph',    icon: <Waypoints size={18} />,     label: 'Knowledge Graph', href: '/graph',    feature: 'graph' },
  { id: 'files',    icon: <Folder size={18} />,        label: 'Files',          href: '/files',    feature: 'files' },
  { id: 'lab',      icon: <FlaskConical size={18} />,  label: 'Lab',            href: '/lab',         feature: 'agents' },
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
  } = useWorkspaceStore();

  const { fetchFiles, fetchLabFiles, setActiveSource } = useFilesStore();
  const { fetchItems: fetchOntology } = useOntologyStore();

  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canAgents = useFeature('agents');
  const canApps = useFeature('apps');
  const canMarketplace = useFeature('marketplace');
  const canSearch = useFeature('search');
  const canOntology = useFeature('ontology');
  const canGraph = useFeature('graph');
  const canSettingsWorkspace = useFeature('settings.workspace');
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);

  useEffect(() => {
    setMounted(true);
    if (canFiles) { fetchFiles(); fetchLabFiles(); }
    if (canOntology) { fetchOntology(); }
  }, [canFiles, canOntology, fetchFiles, fetchLabFiles, fetchOntology]);

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

  // Reconcile activePanelSection with the URL whenever the URL changes
  // (incl. initial mount after rehydration). Without this, a persisted
  // activePanelSection can disagree with the page being rendered.
  const lastReconciledPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (!urlSection) return;
    if (lastReconciledPathRef.current === pathname) return;
    lastReconciledPathRef.current = pathname;
    setActivePanelSection(urlSection.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, urlSection]);

  const currentWorkspace = mounted ? workspaces.find((w) => w.id === currentWorkspaceId) || null : null;
  const displayWorkspaces = mounted ? workspaces : [];

  const isFeatureEnabled = (feature?: SectionDef['feature']) => {
    if (!feature) return true;
    if (feature === 'chat') return !!canChat;
    if (feature === 'files') return !!canFiles;
    if (feature === 'agents') return !!canAgents;
    if (feature === 'apps') return !!canApps;
    if (feature === 'marketplace') return !!canMarketplace;
    if (feature === 'search') return !!canSearch;
    if (feature === 'ontology') return !!canOntology;
    if (feature === 'graph') return !!canGraph;
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
      case 'apps':         return getWorkspacePath(currentWorkspaceId, '/apps');
      case 'marketplace':  return getWorkspacePath(currentWorkspaceId, '/marketplace');
      case 'settings':     return getWorkspacePath(currentWorkspaceId, '/settings');
    }
  };

  const handleSectionClick = (section: SectionDef) => {
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
          {currentWorkspace?.theme?.logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={currentWorkspace.theme.logoUrl} alt={currentWorkspace.name} className="h-full w-full object-cover" />
          ) : (
            <span className="text-sm font-bold text-white">
              {currentWorkspace?.theme?.logoEmoji || currentWorkspace?.icon || currentWorkspace?.name?.charAt(0) || 'N'}
            </span>
          )}
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
        {isSuperadmin && (() => {
          const active = pathname.startsWith('/admin');
          return (
            <button
              key="admin-events"
              onClick={() => router.push('/admin/events')}
              title={!expanded ? 'Platform events' : undefined}
              className={cn(
                'flex items-center rounded-lg transition-all',
                'hover:bg-workspace-accent-10 hover:text-workspace-accent',
                active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-muted-foreground',
                expanded ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center'
              )}
            >
              <span className="flex-shrink-0"><Activity size={18} /></span>
              {expanded && <span className="truncate text-sm font-medium">Platform events</span>}
            </button>
          );
        })()}
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
                  router.push(`/workspace/${workspace.id}/chat`);
                }}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
                  'hover:bg-workspace-accent-10',
                  currentWorkspaceId === workspace.id && 'bg-workspace-accent-5'
                )}
              >
                <div
                  className="flex h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden rounded"
                  style={{ backgroundColor: workspace.theme?.primaryColor || '#22c55e' }}
                >
                  {workspace.theme?.logoUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={workspace.theme.logoUrl} alt={workspace.name} className="h-full w-full object-cover" />
                  ) : (
                    <span className="text-xs text-white">
                      {workspace.theme?.logoEmoji || workspace.icon || workspace.name.charAt(0)}
                    </span>
                  )}
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
