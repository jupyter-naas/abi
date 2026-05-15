'use client';

import { AppWindow } from 'lucide-react';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');

  return (
    <CollapsibleSection
      id="apps"
      icon={<AppWindow size={18} />}
      label="Apps"
      description="Web apps from your installed modules"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    />
  );
}
