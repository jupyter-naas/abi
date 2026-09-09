import { beforeEach, describe, expect, it } from 'vitest';
import { useSlidesStore } from './slides';

describe('slides sidebar filmstrip', () => {
  beforeEach(() => {
    useSlidesStore.setState({
      sidebarView: 'decks',
      selectedIndex: 0,
      filmstrip: null,
      reorderOpenDeck: null,
    });
  });

  it('switches the sidebar between Decks and Filmstrip', () => {
    expect(useSlidesStore.getState().sidebarView).toBe('decks');
    useSlidesStore.getState().setSidebarView('filmstrip');
    expect(useSlidesStore.getState().sidebarView).toBe('filmstrip');
  });

  it('keeps the open-deck selection for the filmstrip and preview', () => {
    useSlidesStore.getState().setSelectedIndex(3);
    expect(useSlidesStore.getState().selectedIndex).toBe(3);
  });

  it('publishes the open deck for the sidebar strip', () => {
    useSlidesStore.getState().setFilmstrip({
      workspaceId: 'ws-1',
      slug: 'pitch',
      html: '<section></section>',
      disabled: false,
    });
    expect(useSlidesStore.getState().filmstrip?.slug).toBe('pitch');
    useSlidesStore.getState().setFilmstrip(null);
    expect(useSlidesStore.getState().filmstrip).toBeNull();
  });
});
