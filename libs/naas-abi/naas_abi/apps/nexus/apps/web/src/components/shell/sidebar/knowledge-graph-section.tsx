'use client';
import { Waypoints } from 'lucide-react';
import { usePathname, useParams } from 'next/navigation';
import { graphMode } from '@/lib/graph-explorer';
import { CollapsibleSection } from './collapsible-section';
import { GraphExplorerSidebar } from '@/components/graph/explorer/explorer-sidebar';
import { GraphComposerSidebar } from '@/components/graph/explorer/composer-sidebar';

export function KnowledgeGraphSection({collapsed, detailOnly}: {collapsed: boolean; detailOnly?: boolean}) {
  const {workspaceId} = useParams<{workspaceId: string}>();
  const composer = graphMode(usePathname()) === 'composer';
  return <CollapsibleSection id="graph" icon={<Waypoints size={18}/>} label="Knowledge Graph"
    description="Explore instances and compose graph views" href={`/workspace/${workspaceId}/graph`}
    collapsed={collapsed} detailOnly={detailOnly}>
    {composer ? <GraphComposerSidebar key={workspaceId} workspaceId={workspaceId}/> : <GraphExplorerSidebar key={workspaceId} workspaceId={workspaceId}/>}
  </CollapsibleSection>;
}
