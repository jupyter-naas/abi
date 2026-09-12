'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SlidesIndexGallery, SlidesTemplateStrip } from '@/components/slides/slides-index-gallery';
import { invalidateSlidesCover } from '@/components/slides/slides-cover-thumb';
import { SlidesMenuBar } from '@/components/slides/slides-menu-bar';
import { SlidesStatusBar } from '@/components/slides/slides-status-bar';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { pushOfficeCreate, useOfficeCreateStore } from '@/components/office/office-create-state';
import {
  openSlidesAgentPane,
  slidesApiErrorMessage,
} from '@/lib/create-slides-project';
import { useOfficeListRecovery, withOfficeListRetry } from '@/lib/office-list-retry';
import { pickPaneOfficeAgent } from '@/lib/pick-workspace-default-agent';
import { partitionSlidesProjects, patchSlidesProject } from '@/lib/slides-project-actions';
import type { SlidesSeedTemplate } from '@/lib/slides-templates';
import { useAgentsStore } from '@/stores/agents';
import { authFetch } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  SLIDES_DECK_UPDATED_EVENT,
  useSlidesStore,
  type SlidesProject,
} from '@/stores/slides';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';

export default function SlidesIndexPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/slides`;
  const [projects, setProjects] = useState<SlidesProject[]>([]);
  const [templates, setTemplates] = useState<SlidesSeedTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const creating = useOfficeCreateStore((s) => s.kind === 'deck');
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSlidesStore((s) => s.setSelectedTitle);
  const { active, archived } = partitionSlidesProjects(projects);
  const visibleProjects = showArchived ? archived : active;
  const loadGen = useRef(0);

  const onCreateFromTemplate = useCallback(
    (templateId?: string) => {
      pushOfficeCreate(router, 'deck', workspaceId, templateId);
    },
    [workspaceId, router],
  );

  const load = useCallback(
    async (opts?: { quiet?: boolean }) => {
      if (!workspaceId) return;
      const gen = ++loadGen.current;
      const quiet = Boolean(opts?.quiet);
      if (!quiet) {
        setLoading(true);
        setError(null);
      }
      try {
        await withOfficeListRetry(async () => {
          const [projRes, tmplRes] = await Promise.all([
            authFetch(`/api/slides/projects?workspace_id=${encodeURIComponent(workspaceId)}`),
            authFetch(`/api/slides/templates?workspace_id=${encodeURIComponent(workspaceId)}`),
          ]);
          if (gen !== loadGen.current) return;
          if (!projRes.ok) {
            const body = (await projRes.json().catch(() => ({}))) as { detail?: unknown };
            throw new Error(slidesApiErrorMessage(body.detail, `Failed (${projRes.status})`));
          }
          setProjects((await projRes.json()) as SlidesProject[]);
          setError(null);
          if (tmplRes.ok) {
            const body = (await tmplRes.json()) as SlidesSeedTemplate[];
            setTemplates(
              body.map((row) => ({
                ...row,
                slides: row.slides ?? [],
                assets: row.assets ?? [],
              })),
            );
          }
        });
      } catch (e) {
        if (gen !== loadGen.current) return;
        if (!quiet) setError((e as Error).message);
      } finally {
        if (gen !== loadGen.current) return;
        if (!quiet) setLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    setProjects([]);
    void load();
  }, [load]);

  useOfficeListRecovery(load, error);

  // Rebind Slides on the index even when the chat pane is closed. The pane
  // ChatInterface is unmounted then, so a leftover Documents bind would
  // otherwise persist until a deck is opened.
  useEffect(() => {
    const agents = useAgentsStore.getState().agents.filter((a) => a.enabled);
    const slides = pickPaneOfficeAgent(agents, { onSlides: true });
    if (slides && useWorkspaceStore.getState().paneAgent !== slides.id) {
      useWorkspaceStore.getState().setPaneAgent(slides.id);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (archived.length === 0 && showArchived) setShowArchived(false);
  }, [archived.length, showArchived]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const slug = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      invalidateSlidesCover(workspaceId, slug);
      void load({ quiet: true });
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [load, workspaceId]);

  const renameProject = useCallback(
    async (project: SlidesProject, title: string) => {
      setProjects((current) =>
        current.map((row) => (row.slug === project.slug ? { ...row, title } : row)),
      );
      try {
        await patchSlidesProject(workspaceId, project.slug, { title });
      } catch (e) {
        setError((e as Error).message);
        void load({ quiet: true });
      }
    },
    [workspaceId, load],
  );

  const archiveProject = useCallback(
    async (project: SlidesProject) => {
      const nextArchived = !project.archived;
      setProjects((current) =>
        current.map((row) =>
          row.slug === project.slug ? { ...row, archived: nextArchived } : row,
        ),
      );
      try {
        await patchSlidesProject(workspaceId, project.slug, { archived: nextArchived });
      } catch (e) {
        setError((e as Error).message);
        void load({ quiet: true });
      }
    },
    [workspaceId, load],
  );

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Slides"
        nav={
          <SlidesMenuBar
            onNewPresentation={() => onCreateFromTemplate()}
            newDisabled={creating}
          />
        }
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      {creating ? (
        <OfficeCreateLoader kind="deck" phase="creating" />
      ) : (
        <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            <Loader2 size={16} className="mr-2 animate-spin" />
            Loading decks…
          </div>
        ) : (
          <>
            <SlidesTemplateStrip
              templates={templates}
              creating={creating}
              onSelect={(templateId) => void onCreateFromTemplate(templateId)}
            />
            <div className="p-6">
              <div className="mb-4 flex items-center justify-between gap-4">
                <h2 className="text-sm font-medium text-foreground">
                  {showArchived ? 'Archived' : 'Your decks'}
                </h2>
                {archived.length > 0 ? (
                  <div className="flex items-center gap-4">
                    <button
                      type="button"
                      className={`chat-section-label${!showArchived ? '' : ' is-link'}`}
                      onClick={() => setShowArchived(false)}
                    >
                      Slides
                    </button>
                    <button
                      type="button"
                      data-testid="slides-archived-filter"
                      className={`chat-section-label${showArchived ? '' : ' is-link'}`}
                      onClick={() => setShowArchived(true)}
                    >
                      Archived
                    </button>
                  </div>
                ) : null}
              </div>
              {visibleProjects.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  {showArchived ? 'No archived presentations.' : 'No presentations yet.'}
                </p>
              ) : (
                <SlidesIndexGallery
                  projects={visibleProjects}
                  workspaceId={workspaceId}
                  templates={templates}
                  onOpen={(project) => {
                    setSelectedSlug(project.slug);
                    setSelectedTitle(project.title);
                    openSlidesAgentPane({ slug: project.slug, title: project.title });
                    router.push(`${base}/${project.slug}`);
                  }}
                  onRename={(project, title) => void renameProject(project, title)}
                  onArchive={(project) => void archiveProject(project)}
                />
              )}
            </div>
          </>
        )}
        </div>
      )}
      <SlidesStatusBar />
    </div>
  );
}
