'use client';

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Check, Map as MapIcon, Search, MessageSquare, BrainCircuit, Waypoints, Folder, Database, FlaskConical, Code, Presentation, LayoutGrid, Store, Settings, Activity, Boxes,
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFilesStore } from '@/stores/files';
import { useOntologyStore } from '@/stores/ontology';
import {
  DEFAULT_NAV_ORDER,
  dragThresholdPx,
  insertIndexFromPoint,
  LIFT_HOLD_MS,
  mergeNavOrder,
  moveNavItem,
  shiftForReorder,
} from '@/lib/sidebar-nav';
import { getWorkspacePath } from './utils';
import { WorkspaceMark } from '../workspace-mark';
import { getWorkspaceSwitchPath } from '@/lib/feature-access';
import { markAppsSkipRestore, clearAppsSkipRestore } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';

type SectionDef = {
  id: SidebarSection;
  icon: React.ReactNode;
  label: string;
  href: string;
  feature?: 'maps' | 'chat' | 'files' | 'datasets' | 'agents' | 'apps' | 'marketplace' | 'search' | 'ontology' | 'graph' | 'code' | 'slides' | 'settings.workspace';
  extraHref?: string;
};

const SECTIONS: SectionDef[] = [
  { id: 'apps',        icon: <LayoutGrid size={18} />,    label: 'Apps',        href: '/apps',        feature: 'apps' },
  { id: 'lab',         icon: <FlaskConical size={18} />,  label: 'Lab',         href: '/lab',         feature: 'agents' },
  { id: 'files',       icon: <Folder size={18} />,        label: 'Files',       href: '/files',       feature: 'files' },
  { id: 'chat',        icon: <MessageSquare size={18} />, label: 'Chat',        href: '/chat',        feature: 'chat' },
  { id: 'search',      icon: <Search size={18} />,        label: 'Search',      href: '/search',      feature: 'search' },
  { id: 'maps',        icon: <MapIcon size={18} />,       label: 'Maps',        href: '/maps',        feature: 'maps' },
  { id: 'ontology',    icon: <BrainCircuit size={18} />,  label: 'Ontology',    href: '/ontology',    feature: 'ontology' },
  { id: 'graph',       icon: <Waypoints size={18} />,     label: 'Knowledge Graph', href: '/graph', feature: 'graph' },
  { id: 'datasets',    icon: <Database size={18} />,      label: 'Datasets',    href: '/datasets',    feature: 'datasets' },
  { id: 'slides',      icon: <Presentation size={18} />,  label: 'Slides',      href: '/slides',      feature: 'slides' },
  { id: 'code',        icon: <Code size={18} />,          label: 'Code',        href: '/code',        feature: 'code' },
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
  const [draggingId, setDraggingId] = useState<SidebarSection | null>(null);
  const [pressedId, setPressedId] = useState<SidebarSection | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const workspaceBtnRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const ghostRef = useRef<HTMLDivElement>(null);
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropIndexRef = useRef<number | null>(null);
  const itemDragRef = useRef<{
    id: SidebarSection;
    fromIndex: number;
    startX: number;
    startY: number;
    originLeft: number;
    originTop: number;
    width: number;
    height: number;
    slot: number;
    origins: number[];
    sizes: number[];
    pointerId: number;
    lifted: boolean;
    lastX: number;
    lastY: number;
  } | null>(null);
  const didDragRef = useRef(false);
  const router = useRouter();
  const pathname = usePathname();

  const {
    workspaces,
    currentWorkspaceId,
    activePanelSection,
    setActivePanelSection,
    setCurrentWorkspace,
    sidebarNavOrder,
    setSidebarNavOrder,
  } = useWorkspaceStore();

  const { fetchFiles, fetchLabFiles, setActiveSource } = useFilesStore();
  const { fetchItems: fetchOntology } = useOntologyStore();

  const canMaps = useFeature('maps');
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canDatasets = useFeature('datasets');
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

  useEffect(() => () => {
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

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

  const lastReconciledPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (lastReconciledPathRef.current === pathname) return;
    lastReconciledPathRef.current = pathname;
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
    if (feature === 'datasets') return !!canDatasets;
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

  const isSectionActive = (section: SectionDef) => {
    const base = getWorkspacePath(currentWorkspaceId, section.href);
    if (pathname.startsWith(base)) return true;
    if (section.extraHref) {
      const extra = getWorkspacePath(currentWorkspaceId, section.extraHref);
      if (pathname.startsWith(extra)) return true;
    }
    return false;
  };

  const orderedSections = useMemo(() => {
    const order = mergeNavOrder(sidebarNavOrder, DEFAULT_NAV_ORDER);
    const index = new Map<string, number>(order.map((id, i) => [id, i]));
    return SECTIONS
      .filter((s) => isFeatureEnabled(s.feature))
      .sort((a, b) => (index.get(a.id) ?? 999) - (index.get(b.id) ?? 999));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidebarNavOrder, canMaps, canChat, canFiles, canDatasets, canAgents, canApps, canMarketplace, canSearch, canOntology, canGraph, canCode, canSlides]);

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
      case 'datasets': return getWorkspacePath(currentWorkspaceId, '/datasets');
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

  const measureDropIndex = useCallback((clientY: number) => {
    const drag = itemDragRef.current;
    if (drag?.origins.length) {
      return insertIndexFromPoint(drag.origins, drag.sizes, clientY);
    }
    const root = navRef.current;
    if (!root) return null;
    const nodes = Array.from(root.querySelectorAll<HTMLElement>('[data-nav-id]'));
    if (nodes.length === 0) return null;
    const origins = nodes.map((el) => el.getBoundingClientRect().top);
    const sizes = nodes.map((el) => el.getBoundingClientRect().height);
    return insertIndexFromPoint(origins, sizes, clientY);
  }, []);

  const placeGhost = (x: number, y: number, scale = 1.12) => {
    const el = ghostRef.current;
    if (!el) return;
    el.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
  };

  useLayoutEffect(() => {
    const drag = itemDragRef.current;
    if (!draggingId || !drag) return;
    placeGhost(
      drag.originLeft + (drag.lastX - drag.startX),
      drag.originTop + (drag.lastY - drag.startY),
    );
  }, [draggingId]);

  const setDrop = (next: number | null) => {
    dropIndexRef.current = next;
    setDropIndex(next);
  };

  const endDragChrome = () => {
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    setPressedId(null);
    setDraggingId(null);
    setDrop(null);
  };

  const liftItem = (clientX: number, clientY: number) => {
    const drag = itemDragRef.current;
    if (!drag || drag.lifted) return;
    drag.lifted = true;
    drag.lastX = clientX;
    drag.lastY = clientY;
    didDragRef.current = true;
    document.body.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';
    setPressedId(null);
    setDraggingId(drag.id);
    setDrop(measureDropIndex(clientY) ?? drag.fromIndex);
  };

  const commitItemDrag = useCallback((id: SidebarSection, insertIndex: number) => {
    const visibleIds = orderedSections.map((s) => s.id);
    const nextVisible = moveNavItem(visibleIds, id, insertIndex);
    setSidebarNavOrder(mergeNavOrder(nextVisible, mergeNavOrder(sidebarNavOrder, DEFAULT_NAV_ORDER)));
  }, [orderedSections, setSidebarNavOrder, sidebarNavOrder]);

  const onItemPointerDown = (section: SectionDef, e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const btn = e.currentTarget;
    const rect = btn.getBoundingClientRect();
    const root = navRef.current;
    const nodes = root ? Array.from(root.querySelectorAll<HTMLElement>('[data-nav-id]')) : [];
    const origins = nodes.map((el) => el.getBoundingClientRect().top);
    const sizes = nodes.map((el) => el.getBoundingClientRect().height);
    const fromIndex = orderedSections.findIndex((s) => s.id === section.id);
    const slot = origins.length > 1 ? origins[1] - origins[0] : rect.height + 4;
    itemDragRef.current = {
      id: section.id,
      fromIndex,
      startX: e.clientX,
      startY: e.clientY,
      originLeft: rect.left,
      originTop: rect.top,
      width: rect.width,
      height: rect.height,
      slot,
      origins,
      sizes,
      pointerId: e.pointerId,
      lifted: false,
      lastX: e.clientX,
      lastY: e.clientY,
    };
    didDragRef.current = false;
    setPressedId(section.id);
    btn.setPointerCapture(e.pointerId);
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    holdTimerRef.current = setTimeout(() => {
      const live = itemDragRef.current;
      if (!live) return;
      liftItem(live.lastX, live.lastY);
    }, LIFT_HOLD_MS);
  };

  const onItemPointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const drag = itemDragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    drag.lastX = e.clientX;
    drag.lastY = e.clientY;
    const dist = Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY);
    if (!drag.lifted) {
      if (dist < dragThresholdPx()) return;
      if (holdTimerRef.current) {
        clearTimeout(holdTimerRef.current);
        holdTimerRef.current = null;
      }
      liftItem(e.clientX, e.clientY);
    }
    placeGhost(
      drag.originLeft + (e.clientX - drag.startX),
      drag.originTop + (e.clientY - drag.startY),
    );
    const next = measureDropIndex(e.clientY);
    if (next != null && next !== dropIndexRef.current) setDrop(next);
  };

  const onItemPointerUp = (section: SectionDef, e: React.PointerEvent<HTMLButtonElement>) => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    const drag = itemDragRef.current;
    itemDragRef.current = null;
    const lifted = !!drag?.lifted;
    const insertIndex = dropIndexRef.current;
    endDragChrome();
    if (lifted) {
      if (drag && insertIndex != null) commitItemDrag(drag.id, insertIndex);
      return;
    }
    handleSectionClick(section);
  };

  const onItemPointerCancel = () => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    itemDragRef.current = null;
    endDragChrome();
  };

  const openWorkspaceMenu = () => {
    if (!workspaceBtnRef.current) return;
    const rect = workspaceBtnRef.current.getBoundingClientRect();
    setDropdownPos({ top: rect.top, left: rect.right + 8 });
    setWorkspaceMenuOpen(true);
  };

  const handleAsideClick = (e: React.MouseEvent<HTMLElement>) => {
    if (e.target === e.currentTarget) setExpanded((v) => !v);
  };

  const draggingSection = draggingId
    ? orderedSections.find((s) => s.id === draggingId)
    : undefined;
  const dragMetrics = draggingId ? itemDragRef.current : null;

  return (
    <aside
      onClick={handleAsideClick}
      className={cn(
        'glass flex h-full flex-col border-r border-border/50 flex-shrink-0 select-none transition-all duration-300',
        expanded ? 'w-48' : 'w-14'
      )}
    >
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

      <nav
        ref={navRef}
        onClick={handleAsideClick}
        className={cn(
          'flex flex-1 flex-col gap-1 py-3',
          draggingId ? 'overflow-visible' : 'overflow-y-auto',
          expanded ? 'px-2' : 'items-center px-2'
        )}
      >
        {orderedSections.map((section, index) => {
          const active = isSectionActive(section);
          const isDragging = draggingId === section.id;
          const isPressed = pressedId === section.id && !isDragging;
          const fromIndex = itemDragRef.current?.fromIndex ?? -1;
          const slot = itemDragRef.current?.slot ?? 0;
          const shift = draggingId && dropIndex != null && fromIndex >= 0
            ? shiftForReorder(index, fromIndex, dropIndex) * slot
            : 0;
          return (
            <button
              key={section.id}
              data-nav-id={section.id}
              type="button"
              onPointerDown={(e) => onItemPointerDown(section, e)}
              onPointerMove={onItemPointerMove}
              onPointerUp={(e) => onItemPointerUp(section, e)}
              onPointerCancel={onItemPointerCancel}
              onClick={(e) => {
                if (didDragRef.current) {
                  e.preventDefault();
                  e.stopPropagation();
                  didDragRef.current = false;
                }
              }}
              title={!expanded ? section.label : undefined}
              className={cn(
                'flex items-center rounded-lg touch-none',
                'hover:bg-workspace-accent-10 hover:text-workspace-accent',
                active ? 'bg-workspace-accent-15 text-workspace-accent' : 'text-muted-foreground',
                expanded ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center',
                isDragging ? 'cursor-grabbing' : 'cursor-grab',
              )}
              style={{
                transform: isPressed
                  ? 'scale(0.92)'
                  : isDragging
                    ? undefined
                    : shift
                      ? `translateY(${shift}px)`
                      : undefined,
                transition: isDragging ? 'none' : 'transform 160ms ease',
                visibility: isDragging ? 'hidden' : 'visible',
                zIndex: isPressed ? 1 : undefined,
              }}
            >
              <span className="flex-shrink-0 pointer-events-none">{section.icon}</span>
              {expanded && <span className="truncate text-sm font-medium pointer-events-none">{section.label}</span>}
            </button>
          );
        })}
      </nav>

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

      {draggingSection && dragMetrics && mounted && createPortal(
        <div
          ref={ghostRef}
          className={cn(
            'pointer-events-none fixed left-0 top-0 z-[500] flex items-center rounded-none',
            'bg-background text-workspace-accent',
            'shadow-[0_16px_40px_rgba(0,0,0,0.28)] ring-1 ring-border',
            expanded ? 'gap-3 px-3' : 'justify-center',
          )}
          style={{
            width: dragMetrics.width,
            height: dragMetrics.height,
            transform: `translate(${dragMetrics.originLeft}px, ${dragMetrics.originTop}px) scale(1.12)`,
            transformOrigin: 'center center',
            willChange: 'transform',
          }}
        >
          <span className="flex-shrink-0">{draggingSection.icon}</span>
          {expanded && <span className="truncate text-sm font-medium">{draggingSection.label}</span>}
        </div>,
        document.body,
      )}
    </aside>
  );
}
