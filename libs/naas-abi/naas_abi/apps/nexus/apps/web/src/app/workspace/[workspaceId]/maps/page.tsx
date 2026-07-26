'use client';

import { Header } from '@/components/shell/header';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { MapsLibrary } from './components/maps-library';
import './components/maps-components.css';

/**
 * Desktop: /maps is the dataset library.
 * Mobile: /maps is the library list (workspace-layout renders MapsSection);
 * do not mount the library here or it fights the shell list.
 */
export default function MapsIndexPage() {
  const isMobile = useIsMobile();
  if (isMobile) return null;

  return (
    <div className="maps-root">
      <div className="maps-header-gap">
        <Header title="Maps" subtitle="Dataset library" />
      </div>
      <div className="maps-body">
        <MapsLibrary />
      </div>
    </div>
  );
}
