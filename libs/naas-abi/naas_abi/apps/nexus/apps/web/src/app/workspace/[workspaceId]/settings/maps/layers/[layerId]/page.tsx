'use client';

/** Settings → Maps › a layer: its page (`new`: a layer to create, `?for=` its feed). */
import { useParams } from 'next/navigation';
import { MapsSettingsView } from '../../maps-settings';

export default function MapsLayerSettingsPage() {
  const layerId = decodeURIComponent(useParams().layerId as string);
  return <MapsSettingsView key={layerId} layer={layerId} />;
}
