'use client';

import { Store, Bot, ExternalLink, FileText, Network, Workflow, GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

const TYPE_LINKS = [
  { type: 'all', label: 'All', icon: <Store size={14} /> },
  { type: 'agents', label: 'Agents', icon: <Bot size={14} /> },
  { type: 'applications', label: 'Applications', icon: <ExternalLink size={14} /> },
  { type: 'tools', label: 'Tools', icon: <FileText size={14} /> },
  { type: 'ontologies', label: 'Ontologies', icon: <Network size={14} /> },
  { type: 'workflows', label: 'Workflows', icon: <Workflow size={14} /> },
  { type: 'pipelines', label: 'Pipelines', icon: <GitBranch size={14} /> },
] as const;

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const basePath = getWorkspacePath(currentWorkspaceId, '/marketplace');
  const isOnAppsPage = pathname?.includes('/marketplace');
  const activeType = isOnAppsPage ? (searchParams?.get('type') ?? 'all') : null;

  return (
    <CollapsibleSection
      id="apps"
      icon={<Store size={18} />}
      label="Marketplace"
      description="Agents, apps, tools and more"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      {TYPE_LINKS.map(({ type, label, icon }) => (
        <Link
          key={type}
          href={type === 'all' ? basePath : `${basePath}?type=${type}`}
          className={cn(
            'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
            activeType === type
              ? 'bg-muted text-foreground font-medium'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          {icon}
          <span>{label}</span>
        </Link>
      ))}
    </CollapsibleSection>
  );
}
