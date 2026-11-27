'use client';

/** Settings → Maps › a feed: its page (`new`: a feed to create), as an agent's or a skill's. */
import { useParams } from 'next/navigation';
import { MapsSettingsView } from '../../maps-settings';

export default function MapsFeedSettingsPage() {
  const feedId = decodeURIComponent(useParams().feedId as string);
  return <MapsSettingsView key={feedId} feed={feedId} />;
}
