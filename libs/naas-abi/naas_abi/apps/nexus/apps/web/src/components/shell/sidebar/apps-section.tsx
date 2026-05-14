'use client';

import { LayoutGrid, Package, Store, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const isOnAppsPage = pathname?.endsWith('/apps');
  const activeTab = isOnAppsPage ? (searchParams?.get('tab') ?? 'installed') : null;

  return (
    <CollapsibleSection
      id="apps"
      icon={<LayoutGrid size={18} />}
      label="Apps"
      description="Modules and marketplace"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <Link
        href={`${basePath}?tab=installed`}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          activeTab === 'installed'
            ? 'bg-muted text-foreground font-medium'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        <Package size={14} />
        <span>Installed</span>
      </Link>

      <Link
        href={`${basePath}?tab=marketplace`}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          activeTab === 'marketplace'
            ? 'bg-muted text-foreground font-medium'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        <Store size={14} />
        <span>Marketplace</span>
      </Link>

      <Link
        href={`${basePath}?tab=tools`}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          activeTab === 'tools'
            ? 'bg-muted text-foreground font-medium'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        )}
      >
        <Wrench size={14} />
        <span>Tools</span>
      </Link>
    </CollapsibleSection>
  );
}
