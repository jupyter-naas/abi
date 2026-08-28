'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFeature } from '@/hooks/use-feature';

import { ChatSection } from '@/app/workspace/[workspaceId]/chat/components/chat-section';
import { MapsSection } from './maps-section';
import { SearchSection } from './search-section';
import { FilesSection } from './files-section';
import { DatasetsSection } from './datasets-section';
import { LabSection } from './lab-section';
import { OntologySection } from './ontology-section';
import { KnowledgeGraphSection } from './knowledge-graph-section';
import { CodeSection } from './code-section';
import { SlidesSection } from './slides-section';
import { MarketplaceSection } from './marketplace-section';
import { AppsSection } from './apps-section';
import { SettingsSection } from './settings-section';

const SECTION_LABELS: Record<SidebarSection, string> = {
  maps: 'Maps',
  search: 'Search',
  chat: 'Chat',
  ontology: 'Ontology',
  graph: 'Knowledge Graph',
  files: 'Files',
  datasets: 'Datasets',
  lab: 'Lab',
  code: 'Code',
  slides: 'Slides',
  apps: 'Apps',
  marketplace: 'Marketplace',
  settings: 'Settings',
};

function SectionContent({ section }: { section: SidebarSection }) {
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
  const canSlides = useFeature('slides');

  if (section === 'maps' && canMaps) return <MapsSection collapsed={false} detailOnly />;
  if (section === 'search' && canSearch) return <SearchSection collapsed={false} detailOnly />;
  if (section === 'chat' && canChat) return <ChatSection collapsed={false} detailOnly />;
  if (section === 'ontology' && canOntology) return <OntologySection collapsed={false} detailOnly />;
  if (section === 'graph' && canGraph) return <KnowledgeGraphSection collapsed={false} detailOnly />;
  if (section === 'files' && canFiles) return <FilesSection collapsed={false} detailOnly />;
  if (section === 'datasets' && canDatasets) return <DatasetsSection collapsed={false} detailOnly />;
  if (section === 'lab' && canAgents) return <LabSection collapsed={false} detailOnly />;
  if (section === 'code') return <CodeSection collapsed={false} detailOnly />;
  if (section === 'slides' && canSlides) return <SlidesSection collapsed={false} detailOnly />;
  if (section === 'apps' && canApps) return <AppsSection collapsed={false} detailOnly />;
  if (section === 'marketplace' && canMarketplace) return <MarketplaceSection collapsed={false} detailOnly />;
  if (section === 'settings') return <SettingsSection collapsed={false} detailOnly />;
  return null;
}

export function SectionPanel() {
  const activePanelSection = useWorkspaceStore((s) => s.activePanelSection);
  const sectionPanelWidth = useWorkspaceStore((s) => s.sectionPanelWidth);
  const setSectionPanelWidth = useWorkspaceStore((s) => s.setSectionPanelWidth);
  const isOpen = activePanelSection !== null;
  const panelTitle = activePanelSection ? SECTION_LABELS[activePanelSection] : '';

  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);
  const isDraggingRef = useRef(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = e.clientX - dragStartX.current;
      setSectionPanelWidth(dragStartWidth.current + delta);
    };
    const onUp = () => {
      if (!isDraggingRef.current) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [setSectionPanelWidth]);

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartX.current = e.clientX;
      dragStartWidth.current = sectionPanelWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [sectionPanelWidth]
  );

  return (
    <>
      {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
      <div
        className={cn(
          'glass flex flex-col border-r border-border/50 overflow-hidden flex-shrink-0',
          // Disable width transition while dragging so resize stays 1:1 with the pointer
          !isDragging && 'transition-[width] duration-300',
          !isOpen && 'w-0 border-r-0'
        )}
        style={isOpen ? { width: sectionPanelWidth } : undefined}
      >
        {isOpen && activePanelSection && (
          <>
            <div className="flex h-14 flex-shrink-0 items-center border-b border-border/50 px-4">
              <span className="text-sm font-semibold">{panelTitle}</span>
            </div>
            <nav className="flex-1 overflow-y-auto p-2">
              <SectionContent section={activePanelSection} />
            </nav>
          </>
        )}
      </div>
      {isOpen && (
        <div
          className="group relative flex w-2 shrink-0 cursor-col-resize items-center justify-center"
          onMouseDown={handleDragStart}
          title="Drag to resize sidebar"
          aria-label="Resize sidebar"
          role="separator"
          aria-orientation="vertical"
        >
          <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-workspace-accent" />
          <div className="relative z-10 flex flex-col gap-[5px]">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-[3px] w-[3px] rounded-full bg-muted-foreground/40 transition-colors group-hover:bg-workspace-accent"
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
