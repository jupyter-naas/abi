'use client';

/** Settings → Search › a topic: its page, as an agent's or a skill's. */
import { useParams } from 'next/navigation';
import { SearchSettingsView } from '../../search-settings';

export default function SearchTopicSettingsPage() {
  const topicId = decodeURIComponent(useParams().topicId as string);
  return <SearchSettingsView key={topicId} topicId={topicId} />;
}
