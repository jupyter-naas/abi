'use client';

import { useState, useEffect, useRef } from 'react';
import { Check, ChevronsUpDown, PanelLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useFilesStore } from '@/stores/files';
import { useOntologyStore } from '@/stores/ontology';

// Section components
import { ChatSection } from './chat-section';
import { SearchSection } from './search-section';
import { FilesSection } from './files-section';
import { LabSection } from './lab-section';
import { OntologySection } from './ontology-section';
import { KnowledgeGraphSection } from './knowledge-graph-section';
import { AppsSection } from './apps-section';

export function Sidebar() {
  const [mounted, setMounted] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const workspaceMenuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const {
    sidebarCollapsed,
    toggleSidebar,
    workspaces,
    currentWorkspaceId,
    selectWorkspace,
    initializeDemoWorkspace,
  } = useWorkspaceStore();

  const { fetchFiles, fetchLabFiles } = useFilesStore();
  const { fetchItems: fetchOntology } = useOntologyStore();

  useEffect(() => {
    setMounted(true);
    fetchFiles();
    fetchLabFiles();
    fetchOntology();
  }, [fetchFiles, fetchLabFiles, fetchOntology]);

  // Close workspace menu on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (workspaceMenuRef.current && !workspaceMenuRef.current.contains(event.target as Node)) {
        setWorkspaceMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const collapsed = mounted ? sidebarCollapsed : false;
  const currentWorkspace = mounted ? workspaces.find((w) => w.id === currentWorkspaceId) || null : null;
  const displayWorkspaces = mounted ? workspaces : [];

  return (
    <aside
      className={cn(
        'glass flex h-full flex-col border-r border-border/50 transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Workspace Selector */}
      <div
        ref={workspaceMenuRef}
        className={cn(
          'relative flex h-14 items-center gap-3 border-b border-border/50 px-3',
          collapsed && 'justify-center px-2'
        )}
      >
        <button
          onClick={() => {
            if (collapsed) {
              toggleSidebar();
            } else {
              setWorkspaceMenuOpen(!workspaceMenuOpen);
            }
          }}
          className={cn(
            'flex items-center gap-3 rounded-md transition-colors',
            !collapsed && 'hover:bg-muted/50 px-2 py-1.5 -mx-2'
          )}
        >
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg overflow-hidden flex-shrink-0"
            style={{ backgroundColor: currentWorkspace?.theme?.primaryColor || '#22c55e' }}
          >
            {currentWorkspace?.theme?.logoUrl ? (
              <img
                src={currentWorkspace.theme.logoUrl}
                alt={currentWorkspace.name}
                className="h-full w-full object-cover"
              />
            ) : (
              <span className="text-sm font-bold text-white">
                {currentWorkspace?.theme?.logoEmoji || currentWorkspace?.icon || currentWorkspace?.name?.charAt(0) || 'N'}
              </span>
            )}
          </div>
          {!collapsed && (
            <>
              <span
                className="text-sm font-medium truncate w-[120px] text-left text-foreground"
                title={currentWorkspace?.name || 'NEXUS'}
              >
                {currentWorkspace?.name || 'NEXUS'}
              </span>
              <ChevronsUpDown
                size={14}
                className="text-muted-foreground flex-shrink-0"
              />
            </>
          )}
        </button>

        {/* Collapse sidebar button */}
        {!collapsed && (
          <button
            onClick={toggleSidebar}
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-muted hover:text-foreground"
            title="Collapse sidebar"
          >
            <PanelLeft size={16} />
          </button>
        )}

        {/* Workspace dropdown */}
        {workspaceMenuOpen && !collapsed && (
          <div className="glass-card absolute left-2 top-full z-50 mt-1 w-60 py-1">
            <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Workspaces
            </p>
            {displayWorkspaces.map((workspace) => (
              <button
                key={workspace.id}
                onClick={() => {
                  selectWorkspace(workspace.id);
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
                  className="flex h-6 w-6 items-center justify-center rounded overflow-hidden flex-shrink-0"
                  style={{ backgroundColor: workspace.theme?.primaryColor || '#22c55e' }}
                >
                  {workspace.theme?.logoUrl ? (
                    <img
                      src={workspace.theme.logoUrl}
                      alt={workspace.name}
                      className="h-full w-full object-cover"
                    />
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
        )}
      </div>

      {/* Navigation Sections */}
      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        <SearchSection collapsed={collapsed} />
        <ChatSection collapsed={collapsed} />
        <OntologySection collapsed={collapsed} />
        <KnowledgeGraphSection collapsed={collapsed} />
        <FilesSection collapsed={collapsed} />
        <LabSection collapsed={collapsed} />
        <AppsSection collapsed={collapsed} />
      </nav>
    </aside>
  );
}
