'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { ChevronRight, FolderTree, LayoutGrid, Presentation } from 'lucide-react';
import {
  DEFAULT_SLIDES_TEMPLATE_ID,
  openSlidesAgentPane,
  slidesApiErrorMessage,
  startNewPresentation,
} from '@/lib/create-slides-project';
import { partitionSlidesProjects, patchSlidesProject } from '@/lib/slides-project-actions';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import {
  slidesTemplateMenuRows,
  type SlidesSeedTemplate,
} from '@/lib/slides-templates';
import { authFetch } from '@/stores/auth';
import {
  SLIDES_DECK_UPDATED_EVENT,
  useSlidesStore,
  type SlidesFilmstripDeck,
  type SlidesProject,
} from '@/stores/slides';
import { SlidesFilmstrip } from '@/components/slides/slides-filmstrip';
import { clampSlideIndex, parseSlidesOutline } from '@/components/slides/slides-outline';
import { CollapsibleSection } from './collapsible-section';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';
import { SidebarToolbar, SidebarToolbarButton } from './sidebar-toolbar';
import {
  buildSlidesTree,
  initialExpandedSlidesDecks,
  type SlidesProjectTree,
} from './slides-tree';
import { SlidesTreeView } from './slides-tree-view';
import { slidesFilmstripEmptyCopy } from './slides-section-views';
import { getWorkspacePath } from './utils';

/**
 * Slides sidebar: Ontology-style view toolbar, then Decks or Filmstrip.
 *
 * Decks is the file tree. Filmstrip is vertical thumbs for the open deck.
 * Templates hang off the New Slides caret on the Decks view.
 */
export function SlidesSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const routeSlug = typeof params?.slug === 'string' ? params.slug : '';
  const slidesBase = getWorkspacePath(workspaceId, '/slides');
  const [projects, setProjects] = useState<SlidesProject[]>([]);
  const [templates, setTemplates] = useState<SlidesSeedTemplate[]>([]);
  const [trees, setTrees] = useState<Record<string, SlidesProjectTree>>({});
  const [rootExpanded, setRootExpanded] = useState(true);
  const [expandedDecks, setExpandedDecks] = useState<string[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [renamingSlug, setRenamingSlug] = useState<string | null>(null);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const selectedTitle = useSlidesStore((s) => s.selectedTitle);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSlidesStore((s) => s.setSelectedTitle);
  const sidebarView = useSlidesStore((s) => s.sidebarView);
  const setSidebarView = useSlidesStore((s) => s.setSidebarView);
  const selectedIndex = useSlidesStore((s) => s.selectedIndex);
  const setSelectedIndex = useSlidesStore((s) => s.setSelectedIndex);
  const filmstrip = useSlidesStore((s) => s.filmstrip);
  const reorderOpenDeck = useSlidesStore((s) => s.reorderOpenDeck);

  const openSlug = routeSlug || selectedSlug;

  const fetchProjects = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/slides/projects?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (res.ok) setProjects((await res.json()) as SlidesProject[]);
    } catch {
      // ignore
    }
  }, [workspaceId]);

  const fetchTemplates = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/slides/templates?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      const body = (await res.json()) as SlidesSeedTemplate[];
      setTemplates(
        body.map((row) => ({
          ...row,
          slides: row.slides ?? [],
          assets: row.assets ?? [],
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId]);

  /** A deck's own files, fetched when its folder opens. */
  const fetchTree = useCallback(
    async (slug: string) => {
      if (!workspaceId || !slug) return;
      try {
        const res = await authFetch(
          `/api/slides/projects/${encodeURIComponent(slug)}/tree` +
            `?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) return;
        const body = (await res.json()) as SlidesProjectTree;
        setTrees((current) => ({ ...current, [slug]: body }));
      } catch {
        // ignore
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    void fetchProjects();
    void fetchTemplates();
  }, [fetchProjects, fetchTemplates, pathname]);

  // Abi names a still-untitled deck on its first write, so the tree label has
  // to come back from the server instead of waiting for the next navigation.
  // The same write can add a file, so the open deck's tree is refetched too.
  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ slug?: string; title?: string }>).detail;
      const slug = detail?.slug || openSlug || '';
      const title = (detail?.title || '').trim();
      if (title && slug) {
        setProjects((current) =>
          current.map((row) => (row.slug === slug ? { ...row, title } : row)),
        );
        if (selectedSlug === slug || openSlug === slug) setSelectedTitle(title);
      }
      void fetchProjects();
      if (slug) void fetchTree(slug);
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchProjects, fetchTree, openSlug, selectedSlug, setSelectedTitle]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  // The deck being edited starts open, the way an editor reveals the file it
  // has loaded.
  useEffect(() => {
    if (!openSlug) return;
    setExpandedDecks((current) =>
      current.includes(openSlug) ? current : [...current, ...initialExpandedSlidesDecks(openSlug)],
    );
  }, [openSlug]);

  useEffect(() => {
    for (const slug of expandedDecks) {
      if (!trees[slug]) void fetchTree(slug);
    }
  }, [expandedDecks, trees, fetchTree]);

  const { active, archived } = useMemo(() => partitionSlidesProjects(projects), [projects]);
  const openIsArchived = Boolean(openSlug && archived.some((row) => row.slug === openSlug));

  const decks = useMemo(
    () =>
      buildSlidesTree(active, {
        workspaceId,
        openSlug: openIsArchived ? null : openSlug,
        openTitle: openIsArchived ? null : selectedTitle,
        trees,
      }),
    [active, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const archivedDecks = useMemo(
    () =>
      buildSlidesTree(archived, {
        workspaceId,
        openSlug: openIsArchived ? openSlug : null,
        openTitle: openIsArchived ? selectedTitle : null,
        trees,
      }),
    [archived, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const renameDeck = useCallback(
    async (slug: string, title: string) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, title } : row)),
      );
      if (selectedSlug === slug) setSelectedTitle(title);
      try {
        await patchSlidesProject(workspaceId, slug, { title });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, selectedSlug, setSelectedTitle, fetchProjects],
  );

  const archiveDeck = useCallback(
    async (slug: string, archivedFlag: boolean) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, archived: archivedFlag } : row)),
      );
      try {
        await patchSlidesProject(workspaceId, slug, { archived: archivedFlag });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, fetchProjects],
  );

  const createDeck = useCallback(
    (templateId: string) => {
      if (!workspaceId || creating) return;
      setCreating(true);
      setActionError(null);
      void startNewPresentation(workspaceId, (href) => router.push(href), templateId)
        .then(() => {
          void fetchProjects();
        })
        .catch((e) => {
          setActionError(
            slidesApiErrorMessage((e as Error).message, 'Could not create the deck.'),
          );
        })
        .finally(() => {
          setCreating(false);
        });
    },
    [workspaceId, creating, router, fetchProjects],
  );

  const templateOptions: SidebarNewItemMenuOption[] = slidesTemplateMenuRows(templates).map(
    (row) =>
      row.kind === 'heading'
        ? { id: row.id, label: row.label, heading: true }
        : {
            id: row.id,
            label: row.label,
            swatch: row.swatch,
            onSelect: () => createDeck(row.id),
          },
  );

  return (
    <CollapsibleSection
      id="slides"
      icon={<Presentation size={18} />}
      label="Slides"
      description="Presentations in this workspace"
      href={slidesBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div data-testid="slides-sidebar-views">
        <SidebarToolbar>
          <SidebarToolbarButton
            icon={<FolderTree size={14} />}
            label="Decks"
            active={sidebarView === 'decks'}
            pressed={sidebarView === 'decks'}
            testId="slides-sidebar-view-decks"
            onClick={() => setSidebarView('decks')}
          />
          <SidebarToolbarButton
            icon={<LayoutGrid size={14} />}
            label="Filmstrip"
            active={sidebarView === 'filmstrip'}
            pressed={sidebarView === 'filmstrip'}
            testId="slides-sidebar-view-filmstrip"
            onClick={() => setSidebarView('filmstrip')}
          />
        </SidebarToolbar>
      </div>

      {sidebarView === 'filmstrip' ? (
        filmstrip?.html ? (
          <SlidesSidebarFilmstrip
            filmstrip={filmstrip}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorderOpenDeck?.(fromIndex, toIndex)}
          />
        ) : (
          <p className="px-3 py-4 text-xs text-muted-foreground" data-testid="slides-filmstrip-empty">
            {slidesFilmstripEmptyCopy(Boolean(filmstrip))}
          </p>
        )
      ) : (
        <>
          <SidebarNewItem
            label="New Slides"
            title="New presentation"
            onClick={() => createDeck(DEFAULT_SLIDES_TEMPLATE_ID)}
            disabled={creating}
            menuLabel="Choose a template"
            menuOptions={templateOptions}
            menuOpen={templateMenuOpen}
            onMenuOpenChange={setTemplateMenuOpen}
          />

          {actionError ? <p className="px-2 pb-1 text-xs text-red-600">{actionError}</p> : null}

          <SlidesTreeView
            decks={decks}
            rootHref={slidesBase}
            currentPath={pathname}
            rootExpanded={rootExpanded}
            onToggleRoot={() => setRootExpanded((open) => !open)}
            expandedDecks={expandedDecks}
            onToggleDeck={(slug) =>
              setExpandedDecks((current) =>
                current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
              )
            }
            expandedDirs={expandedDirs}
            onToggleDir={(path) =>
              setExpandedDirs((current) =>
                current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
              )
            }
            onOpenDeck={(deck) => {
              setSelectedSlug(deck.slug);
              setSelectedTitle(deck.label);
              openSlidesAgentPane({ slug: deck.slug, title: deck.label });
            }}
            renamingSlug={renamingSlug}
            onStartRename={(slug) => setRenamingSlug(slug)}
            onRename={(slug, title) => {
              void renameDeck(slug, title);
              setRenamingSlug(null);
            }}
            onCancelRename={() => setRenamingSlug(null)}
            onArchive={(slug) => void archiveDeck(slug, true)}
          />

          {archived.length > 0 ? (
            <div className="chat-section-group">
              <button
                type="button"
                data-testid="slides-archived-toggle"
                onClick={() => setShowArchived((open) => !open)}
                className="chat-section-show-more"
              >
                <ChevronRight
                  size={12}
                  className={`chat-section-show-more-chevron${showArchived ? ' is-expanded' : ''}`}
                />
                <span>Archived</span>
              </button>
              {showArchived ? (
                <SlidesTreeView
                  decks={archivedDecks}
                  rootHref={slidesBase}
                  currentPath={pathname}
                  rootExpanded
                  onToggleRoot={() => {}}
                  hideRoot
                  emptyLabel="No archived presentations"
                  expandedDecks={expandedDecks}
                  onToggleDeck={(slug) =>
                    setExpandedDecks((current) =>
                      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
                    )
                  }
                  expandedDirs={expandedDirs}
                  onToggleDir={(path) =>
                    setExpandedDirs((current) =>
                      current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
                    )
                  }
                  onOpenDeck={(deck) => {
                    setSelectedSlug(deck.slug);
                    setSelectedTitle(deck.label);
                    openSlidesAgentPane({ slug: deck.slug, title: deck.label });
                  }}
                  renamingSlug={renamingSlug}
                  onStartRename={(slug) => setRenamingSlug(slug)}
                  onRename={(slug, title) => {
                    void renameDeck(slug, title);
                    setRenamingSlug(null);
                  }}
                  onCancelRename={() => setRenamingSlug(null)}
                  onArchive={(slug) => void archiveDeck(slug, false)}
                />
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </CollapsibleSection>
  );
}

function SlidesSidebarFilmstrip({
  filmstrip,
  selectedIndex,
  onSelect,
  onReorder,
}: {
  filmstrip: SlidesFilmstripDeck;
  selectedIndex: number;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const slides = parseSlidesOutline(filmstrip.html);
  return (
    <SlidesFilmstrip
      html={filmstrip.html}
      workspaceId={filmstrip.workspaceId}
      slug={filmstrip.slug}
      slides={slides}
      selectedIndex={clampSlideIndex(selectedIndex, slides.length)}
      disabled={filmstrip.disabled}
      onSelect={onSelect}
      onReorder={onReorder}
    />
  );
}
