'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { DocumentsIndexGallery, SectionsTemplateStrip } from '@/components/documents/documents-index-gallery';
import { invalidateSectionsCover } from '@/components/documents/documents-cover-thumb';
import { DocumentsMenuBar } from '@/components/documents/documents-menu-bar';
import { DocumentsStatusBar } from '@/components/documents/documents-status-bar';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { pushOfficeCreate, useOfficeCreateStore } from '@/components/office/office-create-state';
import {
  openDocumentsAgentPane,
  documentsApiErrorMessage,
} from '@/lib/create-documents-project';
import { partitionDocumentsProjects, patchDocumentsProject } from '@/lib/documents-project-actions';
import type { DocumentsSeedTemplate } from '@/lib/documents-templates';
import { useOfficeListRecovery, withOfficeListRetry } from '@/lib/office-list-retry';
import { pickPaneOfficeAgent } from '@/lib/pick-workspace-default-agent';
import { useAgentsStore } from '@/stores/agents';
import { authFetch } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  DOCUMENTS_UPDATED_EVENT,
  useDocumentsStore,
  type DocumentsProject,
} from '@/stores/documents';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';

export default function SectionsIndexPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/documents`;
  const [projects, setProjects] = useState<DocumentsProject[]>([]);
  const [templates, setTemplates] = useState<DocumentsSeedTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const creating = useOfficeCreateStore((s) => s.kind === 'document');
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const setSelectedSlug = useDocumentsStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useDocumentsStore((s) => s.setSelectedTitle);
  const { active, archived } = partitionDocumentsProjects(projects);
  const visibleProjects = showArchived ? archived : active;
  const loadGen = useRef(0);

  const onCreateFromTemplate = useCallback(
    (templateId?: string) => {
      pushOfficeCreate(router, 'document', workspaceId, templateId);
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
            authFetch(`/api/documents/projects?workspace_id=${encodeURIComponent(workspaceId)}`),
            authFetch(`/api/documents/templates?workspace_id=${encodeURIComponent(workspaceId)}`),
          ]);
          if (gen !== loadGen.current) return;
          if (!projRes.ok) {
            if (projRes.status === 404) {
              setProjects([]);
              setError(null);
              return;
            }
            const body = (await projRes.json().catch(() => ({}))) as { detail?: unknown };
            throw new Error(documentsApiErrorMessage(body.detail, `Failed (${projRes.status})`));
          }
          setProjects((await projRes.json()) as DocumentsProject[]);
          setError(null);
          if (tmplRes.ok) {
            const body = (await tmplRes.json()) as DocumentsSeedTemplate[];
            setTemplates(
              body.map((row) => ({
                ...row,
                sections: row.sections ?? [],
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

  // Rebind Documents on the index even when the chat pane is closed. The pane
  // ChatInterface is unmounted then, so a leftover Slides bind would
  // otherwise persist until a document is opened.
  useEffect(() => {
    const agents = useAgentsStore.getState().agents.filter((a) => a.enabled);
    const documents = pickPaneOfficeAgent(agents, { onDocuments: true });
    if (documents && useWorkspaceStore.getState().paneAgent !== documents.id) {
      useWorkspaceStore.getState().setPaneAgent(documents.id);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (archived.length === 0 && showArchived) setShowArchived(false);
  }, [archived.length, showArchived]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const slug = (event as CustomEvent<{ slug?: string }>).detail?.slug;
      invalidateSectionsCover(workspaceId, slug);
      void load({ quiet: true });
    };
    window.addEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
  }, [load, workspaceId]);

  const renameProject = useCallback(
    async (project: DocumentsProject, title: string) => {
      setProjects((current) =>
        current.map((row) => (row.slug === project.slug ? { ...row, title } : row)),
      );
      try {
        await patchDocumentsProject(workspaceId, project.slug, { title });
      } catch (e) {
        setError((e as Error).message);
        void load({ quiet: true });
      }
    },
    [workspaceId, load],
  );

  const archiveProject = useCallback(
    async (project: DocumentsProject) => {
      const nextArchived = !project.archived;
      setProjects((current) =>
        current.map((row) =>
          row.slug === project.slug ? { ...row, archived: nextArchived } : row,
        ),
      );
      try {
        await patchDocumentsProject(workspaceId, project.slug, { archived: nextArchived });
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
        title="Documents"
        nav={
          <DocumentsMenuBar
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
        <OfficeCreateLoader kind="document" phase="creating" />
      ) : (
        <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            <Loader2 size={16} className="mr-2 animate-spin" />
            Loading documents…
          </div>
        ) : (
          <>
            <SectionsTemplateStrip
              templates={templates}
              creating={creating}
              onSelect={(templateId) => void onCreateFromTemplate(templateId)}
            />
            <div className="p-6">
              <div className="mb-4 flex items-center justify-between gap-4">
                <h2 className="text-sm font-medium text-foreground">
                  {showArchived ? 'Archived' : 'Your documents'}
                </h2>
                {archived.length > 0 ? (
                  <div className="flex items-center gap-4">
                    <button
                      type="button"
                      className={`chat-section-label${!showArchived ? '' : ' is-link'}`}
                      onClick={() => setShowArchived(false)}
                    >
                      Documents
                    </button>
                    <button
                      type="button"
                      data-testid="sections-archived-filter"
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
                  {showArchived ? 'No archived documents.' : 'No documents yet.'}
                </p>
              ) : (
                <DocumentsIndexGallery
                  projects={visibleProjects}
                  workspaceId={workspaceId}
                  templates={templates}
                  onOpen={(project) => {
                    setSelectedSlug(project.slug);
                    setSelectedTitle(project.title);
                    openDocumentsAgentPane({ slug: project.slug, title: project.title });
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
      <DocumentsStatusBar />
    </div>
  );
}
