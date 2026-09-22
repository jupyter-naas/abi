import { beforeEach, describe, expect, it } from 'vitest';
import { isSlidesWriteTool, useSlidesStore } from './slides';

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

describe('isSlidesWriteTool', () => {
  it('recognizes every deck-mutating tool in slides_tools.py', () => {
    expect(isSlidesWriteTool('write_slides_section')).toBe(true);
    expect(isSlidesWriteTool('write_slides_sections')).toBe(true);
    expect(isSlidesWriteTool('write_slides_deck')).toBe(true);
    expect(isSlidesWriteTool('replace_in_slides_deck')).toBe(true);
    expect(isSlidesWriteTool('replace_slide_image')).toBe(true);
    expect(isSlidesWriteTool('insert_slide')).toBe(true);
    expect(isSlidesWriteTool('delete_slide')).toBe(true);
    expect(isSlidesWriteTool('duplicate_slide')).toBe(true);
    expect(isSlidesWriteTool('reorder_slides')).toBe(true);
    expect(isSlidesWriteTool('create_slides_project')).toBe(true);
  });

  it('recognizes shipped publish results by shape, not product tool name', () => {
    const shipped = JSON.stringify({
      ok: true,
      nexus_shipped: true,
      slug: 'palantir',
      title: 'Palantir',
    });
    expect(isSlidesWriteTool('publish_deck', shipped)).toBe(true);
    expect(isSlidesWriteTool('any_custom_publish', shipped)).toBe(true);
    expect(
      isSlidesWriteTool(
        'publish_deck',
        JSON.stringify({ ok: true, nexus_shipped: false, slug: 'x' }),
      ),
    ).toBe(false);
    expect(isSlidesWriteTool('publish_deck')).toBe(false);
  });

  it('ignores read-only and unrelated tools', () => {
    expect(isSlidesWriteTool('read_slides_deck')).toBe(false);
    expect(isSlidesWriteTool('list_slides_projects')).toBe(false);
    expect(isSlidesWriteTool('web_search')).toBe(false);
    expect(isSlidesWriteTool(null)).toBe(false);
    expect(isSlidesWriteTool(undefined)).toBe(false);
  });
});
