'use client';

import { createPortal } from 'react-dom';
import {
  Search, BrainCircuit, Waypoints, Database, Map, Code, Store, Settings, Activity, Boxes, X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';
import { getWorkspacePath } from '../sidebar/utils';
import { shellTokens } from '../tokens';

type MoreItem = {
  id: string;
  label: string;
  icon: React.ReactNode;
  href: string;
  section?: SidebarSection | null;
  feature?: 'maps' | 'search' | 'ontology' | 'graph' | 'datasets' | 'code' | 'marketplace' | 'settings.workspace';
  superadmin?: boolean;
};

const MORE_ITEMS: MoreItem[] = [
  { id: 'maps', label: 'Maps', icon: <Map size={18} />, href: '/maps', section: 'maps', feature: 'maps' },
  { id: 'search', label: 'Search', icon: <Search size={18} />, href: '/search', section: 'search', feature: 'search' },
  { id: 'ontology', label: 'Ontology', icon: <BrainCircuit size={18} />, href: '/ontology', section: 'ontology', feature: 'ontology' },
  { id: 'graph', label: 'Knowledge Graph', icon: <Waypoints size={18} />, href: '/graph/network', section: 'graph', feature: 'graph' },
  { id: 'datasets', label: 'Datasets', icon: <Database size={18} />, href: '/datasets', section: 'datasets', feature: 'datasets' },
  { id: 'code', label: 'Code', icon: <Code size={18} />, href: '/code/workspaces', section: 'code', feature: 'code' },
  { id: 'marketplace', label: 'Marketplace', icon: <Store size={18} />, href: '/marketplace', section: 'marketplace', feature: 'marketplace' },
  { id: 'settings', label: 'Settings', icon: <Settings size={18} />, href: '/settings', section: 'settings', feature: 'settings.workspace' },
  { id: 'admin-events', label: 'Events', icon: <Activity size={18} />, href: '/admin/events', section: null, superadmin: true },
  { id: 'admin-services', label: 'Services', icon: <Boxes size={18} />, href: '/admin/services', section: null, superadmin: true },
];

interface MobileMoreSheetProps {
  open: boolean;
  onClose: () => void;
}

export function MobileMoreSheet({ open, onClose }: MobileMoreSheetProps) {
  const [mounted, setMounted] = useState(false);
  const router = useRouter();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);

  const canMaps = useFeature('maps');
  const canSearch = useFeature('search');
  const canOntology = useFeature('ontology');
  const canGraph = useFeature('graph');
  const canDatasets = useFeature('datasets');
  const canCode = useFeature('code');
  const canMarketplace = useFeature('marketplace');
  const canSettings = useFeature('settings.workspace');

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!mounted || !open) return null;

  const enabled = (item: MoreItem) => {
    if (item.superadmin) return isSuperadmin;
    if (!item.feature) return true;
    if (item.feature === 'maps') return !!canMaps;
    if (item.feature === 'search') return !!canSearch;
    if (item.feature === 'ontology') return !!canOntology;
    if (item.feature === 'graph') return !!canGraph;
    if (item.feature === 'datasets') return !!canDatasets;
    if (item.feature === 'code') return !!canCode;
    if (item.feature === 'marketplace') return !!canMarketplace;
    if (item.feature === 'settings.workspace') return !!canSettings;
    return true;
  };

  const handleItem = (item: MoreItem) => {
    setActivePanelSection(item.section ?? null);
    router.push(getWorkspacePath(currentWorkspaceId, item.href));
    onClose();
  };

  return createPortal(
    // data-org-branded: the portal escapes the shell, where the radius token lives.
    <div
      className="fixed inset-0 z-[300]"
      role="dialog"
      aria-modal="true"
      aria-label="More"
      data-org-branded="true"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        className={cn(
          'absolute inset-x-0 bottom-0 border border-border/60 bg-background shadow-xl',
          'animate-in slide-in-from-bottom duration-200'
        )}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        <div className="flex items-center justify-between px-4 pt-3 pb-2">
          <span className="text-sm font-semibold">More</span>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close more menu"
          >
            <X size={18} />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-1 px-3 pb-4">
          {MORE_ITEMS.filter(enabled).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleItem(item)}
              className="flex flex-col items-center gap-1.5 px-2 py-3 text-muted-foreground transition-colors hover:text-workspace-accent"
            >
              <span className="flex h-10 w-10 items-center justify-center">
                {item.icon}
              </span>
              <span className={shellTokens.mobile.moreSheet.gridLabel}>{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>,
    document.body
  );
}
