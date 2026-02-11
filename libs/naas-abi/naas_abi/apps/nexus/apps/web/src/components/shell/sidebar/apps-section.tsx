'use client';

import { LayoutGrid, Package, Store, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

export function AppsSection({ collapsed }: { collapsed: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();

  return (
    <CollapsibleSection
      id="apps"
      icon={<LayoutGrid size={18} />}
      label="Apps"
      description="Extensions and integrations"
      href={getWorkspacePath(currentWorkspaceId, '/apps')}
      collapsed={collapsed}
    >
      <button
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        <Package size={14} />
        <span>Installed</span>
        <span className="ml-auto text-xs text-muted-foreground">0</span>
      </button>

      <button
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        <Store size={14} />
        <span>Marketplace</span>
        <ExternalLink size={12} className="ml-auto" />
      </button>
    </CollapsibleSection>
  );
}
