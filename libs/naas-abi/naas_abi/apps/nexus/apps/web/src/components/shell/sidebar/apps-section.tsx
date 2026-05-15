'use client';

import { AppWindow, LayoutGrid, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const marketplacePath = getWorkspacePath(currentWorkspaceId, '/marketplace?type=applications');
  const pathname = usePathname();
  const isOnApps = pathname?.includes('/apps');

  return (
    <CollapsibleSection
      id="apps"
      icon={<AppWindow size={18} />}
      label="Apps"
      description="Web apps from your installed modules"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <Link
        href={basePath}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          isOnApps
            ? 'bg-muted text-foreground font-medium'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        )}
      >
        <LayoutGrid size={14} />
        <span>Installed apps</span>
      </Link>

      <Link
        href={marketplacePath}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <ExternalLink size={14} />
        <span>Browse Marketplace</span>
      </Link>
    </CollapsibleSection>
  );
}
