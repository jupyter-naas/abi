'use client';

import { Map } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { MAPS_DATASETS } from '../lib/datasets';
import { mapsDatasetPath, mapsLibraryPath, parseMapsRoute } from '../lib/maps-route';
import './maps-components.css';

export function MapsSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { datasetId } = parseMapsRoute(pathname);

  const openLibrary = () => {
    router.push(mapsLibraryPath(currentWorkspaceId));
  };

  const openDataset = (id: string) => {
    router.push(mapsDatasetPath(currentWorkspaceId, id));
  };

  return (
    <CollapsibleSection
      id="maps"
      icon={<Map size={18} />}
      label="Maps"
      description="Presence and WOG datasets"
      href={getWorkspacePath(currentWorkspaceId, '/maps')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={openLibrary}
    >
      <div className="maps-section-list">
        <button
          type="button"
          className={cn(
            'maps-section-row',
            !datasetId && 'maps-section-row--active',
            isMobilePanel && 'min-h-11 py-2.5',
          )}
          onClick={openLibrary}
        >
          <span>Library</span>
        </button>
        {MAPS_DATASETS.map((dataset) => (
          <button
            key={dataset.id}
            type="button"
            className={cn(
              'maps-section-row',
              datasetId === dataset.id && 'maps-section-row--active',
              isMobilePanel && 'min-h-11 py-2.5',
            )}
            onClick={() => openDataset(dataset.id)}
          >
            <span>{dataset.title}</span>
            {dataset.id === 'presence' && (
              <span className="maps-section-row__meta">primer</span>
            )}
          </button>
        ))}
      </div>
    </CollapsibleSection>
  );
}
