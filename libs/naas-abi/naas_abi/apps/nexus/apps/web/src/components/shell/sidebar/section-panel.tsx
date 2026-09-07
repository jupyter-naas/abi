'use client';

import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFeature } from '@/hooks/use-feature';
import { ColumnResizeHandle, useColumnResize } from '../column-resize-handle';

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
import { WorkspacesSection } from './workspaces-section';

const SECTION_LABELS: Record<SidebarSection, string> = {
  home: 'Home',
  workspaces: 'Workspaces',
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
  if (section === 'workspaces') return <WorkspacesSection />;
  return null;
}

export function SectionPanel() {
  const activePanelSection = useWorkspaceStore((s) => s.activePanelSection);
  const sectionPanelWidth = useWorkspaceStore((s) => s.sectionPanelWidth);
  const setSectionPanelWidth = useWorkspaceStore((s) => s.setSectionPanelWidth);
  const isOpen = activePanelSection !== null;
  const panelTitle = activePanelSection ? SECTION_LABELS[activePanelSection] : '';
  const { isDragging, handleDragStart } = useColumnResize(sectionPanelWidth, setSectionPanelWidth);

  return (
    <>
      {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
      <div
        className={cn(
          'glass flex flex-col border-r border-border/50 overflow-hidden flex-shrink-0',
          !isDragging && 'transition-[width] duration-300',
          !isOpen && 'w-0 border-r-0'
        )}
        style={isOpen ? { width: sectionPanelWidth } : undefined}
      >
        {isOpen && activePanelSection && (
          <>
            <div className="flex h-14 flex-shrink-0 items-center border-b border-border/50 pl-8 pr-4">
              <span className="text-sm font-semibold">{panelTitle}</span>
            </div>
            <nav className="flex-1 overflow-y-auto p-2">
              <SectionContent section={activePanelSection} />
            </nav>
          </>
        )}
      </div>
      {isOpen && (
        <ColumnResizeHandle onMouseDown={handleDragStart} label="Drag to resize column" />
      )}
    </>
  );
}
