'use client';

import { LayoutGrid } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();

  return (
    <CollapsibleSection
      id="apps"
      icon={<LayoutGrid size={18} />}
      label="Apps"
      description="Installed modules and marketplace"
      href={getWorkspacePath(currentWorkspaceId, '/apps')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    />
  );
}
