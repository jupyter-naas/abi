'use client';

import React from 'react';
import {
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  ChevronRight,
  CloudLightning,
  Crosshair,
  Flame,
  Globe,
  Laptop,
  Layers,
  Map,
  MapPin,
  Mountain,
  Newspaper,
  Plane,
  Rocket,
  Satellite,
  Ship,
  Sparkles,
  Thermometer,
  Wind,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useMapsStore } from '@/stores/maps';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from '@/components/shell/sidebar/collapsible-section';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { shellTokens } from '@/components/shell/tokens';
import {
  getMapsDatasetsByCategory,
  MAPS_CATEGORIES,
  type MapsDataset,
} from '../lib/datasets';
import { mapsDatasetPath, mapsLibraryPath, parseMapsRoute } from '../lib/maps-route';
import './maps-components.css';

const mapsIconMap: Record<string, LucideIcon> = {
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  CloudLightning,
  Crosshair,
  Flame,
  Globe,
  Laptop,
  Layers,
  Map,
  MapPin,
  Mountain,
  Newspaper,
  Plane,
  Rocket,
  Satellite,
  Ship,
  Sparkles,
  Thermometer,
  Wind,
};

const MapsDatasetItem = React.memo(function MapsDatasetItem({
  dataset,
  active,
  dense,
  onOpen,
}: {
  dataset: MapsDataset;
  active: boolean;
  dense?: boolean;
  onOpen: () => void;
}) {
  const IconComponent = mapsIconMap[dataset.icon] || Map;

  return (
    <button
      type="button"
      onClick={onOpen}
      title={dataset.description}
      className={cn(
        'maps-section-row group',
        shellTokens.sidebar.listRow,
        active && 'maps-section-row--active',
        dense && 'maps-section-row--dense',
      )}
    >
      <IconComponent size={14} className="maps-section-row__icon" />
      <span className="maps-section-row__label">{dataset.title}</span>
    </button>
  );
});

const MapsCategoryGroup = React.memo(function MapsCategoryGroup({
  label,
  datasets,
  activeDatasetId,
  isExpanded,
  dense,
  onToggle,
  onOpenDataset,
}: {
  label: string;
  datasets: MapsDataset[];
  activeDatasetId: string | null;
  isExpanded: boolean;
  dense?: boolean;
  onToggle: () => void;
  onOpenDataset: (id: string) => void;
}) {
  const activeCount = datasets.filter((d) => d.id === activeDatasetId).length;

  return (
    <div className="maps-category">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          'maps-category__header',
          shellTokens.sidebar.sectionLabel,
        )}
      >
        <ChevronRight
          size={12}
          className={cn(
            'maps-category__chevron',
            isExpanded && 'maps-category__chevron--open',
          )}
        />
        <span className="maps-category__label">{label}</span>
        <span className="maps-category__count">
          {activeCount}/{datasets.length}
        </span>
      </button>
      {isExpanded && (
        <div className="maps-category__items">
          {datasets.length === 0 ? (
            <p className="maps-category__empty">None yet</p>
          ) : (
            datasets.map((dataset) => (
              <MapsDatasetItem
                key={dataset.id}
                dataset={dataset}
                active={activeDatasetId === dataset.id}
                dense={dense}
                onOpen={() => onOpenDataset(dataset.id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
});

export function MapsDatasetGroups({
  dense,
}: {
  /** Larger touch targets for mobile panel / library list. */
  dense?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { datasetId } = parseMapsRoute(pathname);
  const { expandedCategories, toggleCategory } = useMapsStore();

  const openDataset = (id: string) => {
    router.push(mapsDatasetPath(currentWorkspaceId, id));
  };

  return (
    <div className="maps-section-list">
      {MAPS_CATEGORIES.map(({ id, label }) => {
        const datasets = getMapsDatasetsByCategory(id);
        // Hide empty buckets (Custom stays empty upstream until a product overlay injects datasets).
        if (datasets.length === 0) return null;
        return (
          <MapsCategoryGroup
            key={id}
            label={label}
            datasets={datasets}
            activeDatasetId={datasetId}
            isExpanded={expandedCategories.includes(id)}
            dense={dense}
            onToggle={() => toggleCategory(id)}
            onOpenDataset={openDataset}
          />
        );
      })}
    </div>
  );
}

export function MapsSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  const openLibrary = () => {
    router.push(mapsLibraryPath(currentWorkspaceId));
  };

  return (
    <CollapsibleSection
      id="maps"
      icon={<Map size={18} />}
      label="Maps"
      description="Public and private map sources"
      href={getWorkspacePath(currentWorkspaceId, '/maps')}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={openLibrary}
    >
      <MapsDatasetGroups dense={isMobilePanel} />
    </CollapsibleSection>
  );
}
