'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { Presentation } from 'lucide-react';
import {
  DEFAULT_SLIDES_TEMPLATE_ID,
  slidesApiErrorMessage,
  startNewPresentation,
} from '@/lib/create-slides-project';
import type { SlidesSeedTemplate } from '@/lib/slides-templates';
import { authFetch } from '@/stores/auth';
import {
  SLIDES_DECK_UPDATED_EVENT,
  useSlidesStore,
  type SlidesProject,
} from '@/stores/slides';
import { CollapsibleSection } from './collapsible-section';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';
import {
  buildSlidesTree,
  initialExpandedSlidesDecks,
  type SlidesProjectTree,
} from './slides-tree';
import { SlidesTreeView } from './slides-tree-view';
import { getWorkspacePath } from './utils';

/**
 * Slides sidebar: a create action and a file tree, nothing else.
 *
 * Templates used to own a section here, which meant browsing them was a
 * separate step from making a deck. They now hang off New Slides, so picking
 * one is part of creating. What is left below is a plain explorer over the
 * decks that exist in the workspace repo.
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
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSlidesStore((s) => s.setSelectedTitle);

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
      void fetchProjects();
      const slug =
        (event as CustomEvent<{ slug?: string }>).detail?.slug || openSlug || '';
      if (slug) void fetchTree(slug);
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchProjects, fetchTree, openSlug]);

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

  const decks = useMemo(
    () => buildSlidesTree(projects, { workspaceId, openSlug, trees }),
    [projects, workspaceId, openSlug, trees],
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

  const templateOptions: SidebarNewItemMenuOption[] = templates.map((template) => ({
    id: template.id,
    label: template.name,
    swatch: template.preview_accent || template.preview_bg,
    onSelect: () => createDeck(template.id),
  }));

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
        }}
      />
    </CollapsibleSection>
  );
}
