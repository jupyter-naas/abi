'use client';

import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { useFeature } from '@/hooks/use-feature';

import { ChatSection } from './chat-section';
import { SearchSection } from './search-section';
import { FilesSection } from './files-section';
import { LabSection } from './lab-section';
import { OntologySection } from './ontology-section';
import { KnowledgeGraphSection } from './knowledge-graph-section';
import { MarketplaceSection } from './marketplace-section';
import { AppsSection } from './apps-section';

const SECTION_LABELS: Record<SidebarSection, string> = {
  search: 'Search',
  chat: 'Chat',
  ontology: 'Ontology',
  graph: 'Knowledge Graph',
  files: 'Files',
  lab: 'Lab',
  apps: 'Apps',
  marketplace: 'Marketplace',
};

function SectionContent({ section }: { section: SidebarSection }) {
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canAgents = useFeature('agents');
  const canKnowledge = useFeature('knowledge');

  if (section === 'search' && canKnowledge) return <SearchSection collapsed={false} detailOnly />;
  if (section === 'chat' && canChat) return <ChatSection collapsed={false} detailOnly />;
  if (section === 'ontology' && canKnowledge) return <OntologySection collapsed={false} detailOnly />;
  if (section === 'graph' && canKnowledge) return <KnowledgeGraphSection collapsed={false} detailOnly />;
  if (section === 'files' && canFiles) return <FilesSection collapsed={false} detailOnly />;
  if (section === 'lab' && canAgents) return <LabSection collapsed={false} detailOnly />;
  if (section === 'apps' && canAgents) return <AppsSection collapsed={false} detailOnly />;
  if (section === 'marketplace' && canAgents) return <MarketplaceSection collapsed={false} detailOnly />;
  return null;
}

export function SectionPanel() {
  const { activePanelSection } = useWorkspaceStore();
  const isOpen = activePanelSection !== null;
  const panelTitle = activePanelSection ? SECTION_LABELS[activePanelSection] : '';

  return (
    <div
      className={cn(
        'glass flex flex-col border-r border-border/50 transition-all duration-300 overflow-hidden flex-shrink-0',
        isOpen ? 'w-64' : 'w-0'
      )}
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
  );
}
