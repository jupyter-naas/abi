'use client';

import { Map, MessageSquare, Folder, LayoutGrid, MoreHorizontal } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore } from '@/stores/workspace';
import { getWorkspacePath } from '../sidebar/utils';

type MobileTab = 'maps' | 'chat' | 'files' | 'apps' | 'more';

type TabDef = {
  id: MobileTab;
  label: string;
  icon: React.ReactNode;
  href?: string;
  feature?: 'maps' | 'chat' | 'files' | 'apps';
};

const TABS: TabDef[] = [
  { id: 'maps', label: 'Maps', icon: <Map size={20} />, href: '/maps', feature: 'maps' },
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={20} />, href: '/chat', feature: 'chat' },
  { id: 'files', label: 'Files', icon: <Folder size={20} />, href: '/files', feature: 'files' },
  { id: 'apps', label: 'Apps', icon: <LayoutGrid size={20} />, href: '/apps', feature: 'apps' },
  { id: 'more', label: 'More', icon: <MoreHorizontal size={20} /> },
];

interface MobileBottomNavProps {
  moreOpen: boolean;
  onMoreToggle: () => void;
}

export function MobileBottomNav({ moreOpen, onMoreToggle }: MobileBottomNavProps) {
  const router = useRouter();
  const pathname = usePathname();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const setActiveConversation = useWorkspaceStore((s) => s.setActiveConversation);
  const setMobilePendingChatSlug = useWorkspaceStore((s) => s.setMobilePendingChatSlug);

  const canMaps = useFeature('maps');
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');
  const canApps = useFeature('apps');

  const enabled = (feature?: TabDef['feature']) => {
    if (!feature) return true;
    if (feature === 'maps') return !!canMaps;
    if (feature === 'chat') return !!canChat;
    if (feature === 'files') return !!canFiles;
    if (feature === 'apps') return !!canApps;
    return true;
  };

  const isTabActive = (tab: TabDef) => {
    if (tab.id === 'more') return moreOpen;
    if (tab.id === 'maps') return pathname.includes('/maps');
    if (tab.id === 'chat') return pathname.includes('/chat');
    if (tab.id === 'files') return pathname.includes('/files');
    if (tab.id === 'apps') return pathname.includes('/apps');
    return false;
  };

  const handleTab = (tab: TabDef) => {
    if (tab.id === 'more') {
      onMoreToggle();
      return;
    }
    if (moreOpen) onMoreToggle();

    if (tab.id === 'maps') {
      setActivePanelSection('maps');
      router.push(getWorkspacePath(currentWorkspaceId, '/maps'));
      return;
    }

    if (tab.id === 'chat') {
      // Teams-style: Chat tab always returns to the conversation list.
      setActiveConversation(null);
      setMobilePendingChatSlug(null);
      setActivePanelSection('chat');
      router.push(getWorkspacePath(currentWorkspaceId, '/chat'));
      return;
    }

    if (tab.id === 'files') {
      setActivePanelSection('files');
      router.push(getWorkspacePath(currentWorkspaceId, '/files'));
      return;
    }
    if (tab.id === 'apps') {
      setActivePanelSection('apps');
      router.push(getWorkspacePath(currentWorkspaceId, '/apps'));
    }
  };

  return (
    <nav
      className="flex flex-shrink-0 items-stretch border-t border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      aria-label="Primary"
    >
      {TABS.filter((t) => enabled(t.feature)).map((tab) => {
        const active = isTabActive(tab);
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => handleTab(tab)}
            className={cn(
              'mobile-bottom-nav-tab flex min-h-[52px] flex-1 flex-col items-center justify-center gap-1 py-2 text-sm font-medium transition-colors',
              active ? 'text-workspace-accent' : 'text-muted-foreground'
            )}
          >
            <span className={cn(active && 'text-workspace-accent')}>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
