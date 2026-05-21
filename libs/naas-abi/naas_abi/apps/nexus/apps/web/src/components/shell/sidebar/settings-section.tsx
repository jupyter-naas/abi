'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';

export function SettingsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const pathname = usePathname();
  const { currentWorkspaceId } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/settings');

  return (
    <CollapsibleSection
      id="settings"
      icon={<Settings size={18} />}
      label="Settings"
      description="Workspace configuration"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="space-y-0.5">
        {SETTINGS_GROUPS.map((group) => (
          <div key={group.label} className="space-y-0.5">
            <p className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group.label}
            </p>
            {group.items.map((item) => {
              const fullHref = getWorkspacePath(currentWorkspaceId, item.href);
              const isActive = pathname === fullHref || pathname.endsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={fullHref}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                    isActive
                      ? 'bg-workspace-accent-15 text-workspace-accent'
                      : 'text-muted-foreground hover:bg-workspace-accent-10 hover:text-foreground'
                  )}
                >
                  <Icon size={14} className="flex-shrink-0" />
                  <span className="flex-1 truncate text-left">{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </CollapsibleSection>
  );
}
