'use client';

import { LayoutGrid } from 'lucide-react';
import { SLIDES_KIND } from '@/components/office/office-kinds';
import { SlidesFilmstrip } from '@/components/slides/slides-filmstrip';
import { clampSlideIndex, parseSlidesOutline } from '@/components/slides/slides-outline';
import { openSlidesAgentPane } from '@/lib/create-slides-project';
import { patchSlidesProject } from '@/lib/slides-project-actions';
import { SLIDES_DECK_UPDATED_EVENT, useSlidesStore, type SlidesSidebarView } from '@/stores/slides';
import { OfficeSection, type OfficeSectionConfig } from './office-section';

export const SLIDES_SECTION: OfficeSectionConfig<SlidesSidebarView> = {
  kind: SLIDES_KIND,
  useStore: useSlidesStore,
  updatedEvent: SLIDES_DECK_UPDATED_EVENT,
  label: 'Slides',
  description: 'Presentations in this workspace',
  views: {
    tree: { id: 'decks', label: 'Decks' },
    detail: {
      id: 'filmstrip',
      label: 'Filmstrip',
      icon: <LayoutGrid size={14} />,
      loading: 'Loading slides…',
      empty: 'Open a deck to see slides.',
    },
  },
  newItem: { label: 'New Slides', title: 'New presentation' },
  create: { overlay: 'deck' },
  patch: patchSlidesProject,
  openAgentPane: openSlidesAgentPane,
};

/** Slides sidebar: the file tree, or the open deck's slides. */
export function SlidesSection(props: { collapsed: boolean; detailOnly?: boolean }) {
  const filmstrip = useSlidesStore((s) => s.filmstrip);
  const selectedIndex = useSlidesStore((s) => s.selectedIndex);
  const setSelectedIndex = useSlidesStore((s) => s.setSelectedIndex);
  const reorder = useSlidesStore((s) => s.reorderOpenDeck);
  return (
    <OfficeSection
      {...props}
      config={SLIDES_SECTION}
      hasOpenSession={Boolean(filmstrip)}
      renderDetail={() => {
        if (!filmstrip?.html) return null;
        const slides = parseSlidesOutline(filmstrip.html);
        return (
          <SlidesFilmstrip
            html={filmstrip.html}
            workspaceId={filmstrip.workspaceId}
            slug={filmstrip.slug}
            slides={slides}
            selectedIndex={clampSlideIndex(selectedIndex, slides.length)}
            disabled={filmstrip.disabled}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorder?.(fromIndex, toIndex)}
          />
        );
      }}
    />
  );
}
