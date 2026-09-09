'use client';

import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFeature } from '@/hooks/use-feature';
import { ColumnResizeHandle, useColumnResize } from '../column-resize-handle';

const sectionLoading = () => (
  <div className="px-2 py-3 text-xs text-muted-foreground">Loading…</div>
);

const ChatSection = dynamic(
  () => import('@/app/workspace/[workspaceId]/chat/components/chat-section').then((m) => m.ChatSection),
  { ssr: false, loading: sectionLoading },
);
const MapsSection = dynamic(() => import('./maps-section').then((m) => m.MapsSection), {
  ssr: false,
  loading: sectionLoading,
});
const SearchSection = dynamic(() => import('./search-section').then((m) => m.SearchSection), {
  ssr: false,
  loading: sectionLoading,
});
const FilesSection = dynamic(() => import('./files-section').then((m) => m.FilesSection), {
  ssr: false,
  loading: sectionLoading,
});
const DatasetsSection = dynamic(() => import('./datasets-section').then((m) => m.DatasetsSection), {
  ssr: false,
  loading: sectionLoading,
});
const OntologySection = dynamic(() => import('./ontology-section').then((m) => m.OntologySection), {
  ssr: false,
  loading: sectionLoading,
});
const KnowledgeGraphSection = dynamic(
  () => import('./knowledge-graph-section').then((m) => m.KnowledgeGraphSection),
  { ssr: false, loading: sectionLoading },
);
const CodeSection = dynamic(() => import('./code-section').then((m) => m.CodeSection), {
  ssr: false,
  loading: sectionLoading,
});
const SlidesSection = dynamic(() => import('./slides-section').then((m) => m.SlidesSection), {
  ssr: false,
  loading: sectionLoading,
});
const MarketplaceSection = dynamic(
  () => import('./marketplace-section').then((m) => m.MarketplaceSection),
  { ssr: false, loading: sectionLoading },
);
const AppsSection = dynamic(() => import('./apps-section').then((m) => m.AppsSection), {
  ssr: false,
  loading: sectionLoading,
});
const SettingsSection = dynamic(() => import('./settings-section').then((m) => m.SettingsSection), {
  ssr: false,
  loading: sectionLoading,
});

function SectionContent({ section }: { section: SidebarSection }) {
  const canMaps = useFeature('maps');
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canDatasets = useFeature('datasets');
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
  if (section === 'code') return <CodeSection collapsed={false} detailOnly />;
  if (section === 'slides' && canSlides) return <SlidesSection collapsed={false} detailOnly />;
  if (section === 'apps' && canApps) return <AppsSection collapsed={false} detailOnly />;
  if (section === 'marketplace' && canMarketplace) return <MarketplaceSection collapsed={false} detailOnly />;
  if (section === 'settings') return <SettingsSection collapsed={false} detailOnly />;
  return null;
}

/**
 * The active section's title used to live in its own row here; it now
 * renders in TopNav (spanning the full app width) so it lines up with the
 * workspace mark instead of duplicating a header per column. See topnav.tsx.
 */
export function SectionPanel() {
  const activePanelSection = useWorkspaceStore((s) => s.activePanelSection);
  const sectionPanelWidth = useWorkspaceStore((s) => s.sectionPanelWidth);
  const setSectionPanelWidth = useWorkspaceStore((s) => s.setSectionPanelWidth);
  const isOpen = activePanelSection !== null;
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
          <nav className="flex-1 overflow-y-auto p-2">
            <SectionContent section={activePanelSection} />
          </nav>
        )}
      </div>
      {isOpen && (
        <ColumnResizeHandle onMouseDown={handleDragStart} label="Drag to resize column" isActive={isDragging} />
      )}
    </>
  );
}
