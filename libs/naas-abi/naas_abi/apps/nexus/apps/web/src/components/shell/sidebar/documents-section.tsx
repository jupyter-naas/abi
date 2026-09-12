'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { ChevronRight, FileText, FolderTree, List } from 'lucide-react';
import { officeCreateHref } from '@/components/office/office-create';
import { openDocumentsAgentPane } from '@/lib/create-documents-project';
import { partitionDocumentsProjects, patchDocumentsProject } from '@/lib/documents-project-actions';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import {
  resolveDocumentsTemplateId,
  sectionsTemplateMenuRows,
  type DocumentsSeedTemplate,
} from '@/lib/documents-templates';
import { authFetch } from '@/stores/auth';
import {
  DOCUMENTS_UPDATED_EVENT,
  useDocumentsStore,
  type DocumentsOutlineDocument,
  type DocumentsProject,
} from '@/stores/documents';
import { DocumentsOutline } from '@/components/documents/documents-filmstrip';
import { clampSectionIndex, parseDocumentsOutline } from '@/components/documents/documents-outline';
import { CollapsibleSection } from './collapsible-section';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';
import { SidebarToolbar, SidebarToolbarButton } from './sidebar-toolbar';
import {
  buildSectionsTree,
  initialExpandedDocuments,
  type DocumentsProjectTree,
} from './documents-tree';
import { SectionsTreeView } from './documents-tree-view';
import { sectionsFilmstripEmptyCopy } from './documents-section-views';
import { getWorkspacePath } from './utils';

/**
 * Documents sidebar: Ontology-style view toolbar, then Documents or Outline.
 *
 * Documents is the file tree. Outline is headings for the open document.
 * Templates hang off the New Documents caret on the Documents view.
 */
export function DocumentsSection({
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
  const sectionsBase = getWorkspacePath(workspaceId, '/documents');
  const [projects, setProjects] = useState<DocumentsProject[]>([]);
  const [templates, setTemplates] = useState<DocumentsSeedTemplate[]>([]);
  const [trees, setTrees] = useState<Record<string, DocumentsProjectTree>>({});
  const [rootExpanded, setRootExpanded] = useState(true);
  const [expandedDocuments, setExpandedDocuments] = useState<string[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const creating = pathname === `${sectionsBase}/new`;
  const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [renamingSlug, setRenamingSlug] = useState<string | null>(null);
  const selectedSlug = useDocumentsStore((s) => s.selectedSlug);
  const selectedTitle = useDocumentsStore((s) => s.selectedTitle);
  const setSelectedSlug = useDocumentsStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useDocumentsStore((s) => s.setSelectedTitle);
  const sidebarView = useDocumentsStore((s) => s.sidebarView);
  const setSidebarView = useDocumentsStore((s) => s.setSidebarView);
  const selectedIndex = useDocumentsStore((s) => s.selectedIndex);
  const setSelectedIndex = useDocumentsStore((s) => s.setSelectedIndex);
  const outline = useDocumentsStore((s) => s.outline);
  const reorderOpenDocument = useDocumentsStore((s) => s.reorderOpenDocument);

  const openSlug = routeSlug || selectedSlug;

  const fetchProjects = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/documents/projects?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (res.ok) setProjects((await res.json()) as DocumentsProject[]);
    } catch {
      // ignore
    }
  }, [workspaceId]);

  const fetchTemplates = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/documents/templates?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      const body = (await res.json()) as DocumentsSeedTemplate[];
      setTemplates(
        body.map((row) => ({
          ...row,
          sections: row.sections ?? [],
          assets: row.assets ?? [],
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId]);

  /** A document's own files, fetched when its folder opens. */
  const fetchTree = useCallback(
    async (slug: string) => {
      if (!workspaceId || !slug) return;
      try {
        const res = await authFetch(
          `/api/documents/projects/${encodeURIComponent(slug)}/tree` +
            `?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) return;
        const body = (await res.json()) as DocumentsProjectTree;
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

  // Abi names a still-untitled document on its first write, so the tree label has
  // to come back from the server instead of waiting for the next navigation.
  // The same write can add a file, so the open document's tree is refetched too.
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
    window.addEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
  }, [fetchProjects, fetchTree, openSlug, selectedSlug, setSelectedTitle]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  // The document being edited starts open, the way an editor reveals the file it
  // has loaded.
  useEffect(() => {
    if (!openSlug) return;
    setExpandedDocuments((current) =>
      current.includes(openSlug) ? current : [...current, ...initialExpandedDocuments(openSlug)],
    );
  }, [openSlug]);

  useEffect(() => {
    for (const slug of expandedDocuments) {
      if (!trees[slug]) void fetchTree(slug);
    }
  }, [expandedDocuments, trees, fetchTree]);

  const { active, archived } = useMemo(() => partitionDocumentsProjects(projects), [projects]);
  const openIsArchived = Boolean(openSlug && archived.some((row) => row.slug === openSlug));

  const documents = useMemo(
    () =>
      buildSectionsTree(active, {
        workspaceId,
        openSlug: openIsArchived ? null : openSlug,
        openTitle: openIsArchived ? null : selectedTitle,
        trees,
      }),
    [active, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const archivedDocuments = useMemo(
    () =>
      buildSectionsTree(archived, {
        workspaceId,
        openSlug: openIsArchived ? openSlug : null,
        openTitle: openIsArchived ? selectedTitle : null,
        trees,
      }),
    [archived, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const renameDocument = useCallback(
    async (slug: string, title: string) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, title } : row)),
      );
      if (selectedSlug === slug) setSelectedTitle(title);
      try {
        await patchDocumentsProject(workspaceId, slug, { title });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, selectedSlug, setSelectedTitle, fetchProjects],
  );

  const archiveDocument = useCallback(
    async (slug: string, archivedFlag: boolean) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, archived: archivedFlag } : row)),
      );
      try {
        await patchDocumentsProject(workspaceId, slug, { archived: archivedFlag });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, fetchProjects],
  );

  const createDocument = useCallback(
    (templateId?: string) => {
      if (!workspaceId || creating) return;
      setActionError(null);
      router.push(officeCreateHref('document', workspaceId, templateId));
    },
    [workspaceId, creating, router],
  );

  const templateOptions: SidebarNewItemMenuOption[] = sectionsTemplateMenuRows(templates).map(
    (row) =>
      row.kind === 'heading'
        ? { id: row.id, label: row.label, heading: true }
        : {
            id: row.id,
            label: row.label,
            swatch: row.swatch,
            onSelect: () => createDocument(row.id),
          },
  );

  return (
    <CollapsibleSection
      id="documents"
      icon={<FileText size={18} />}
      label="Documents"
      description="Documents in this workspace"
      href={sectionsBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div data-testid="sections-sidebar-views">
        <SidebarToolbar>
          <SidebarToolbarButton
            icon={<FolderTree size={14} />}
            label="Documents"
            active={sidebarView === 'documents'}
            pressed={sidebarView === 'documents'}
            testId="sections-sidebar-view-documents"
            onClick={() => setSidebarView('documents')}
          />
          <SidebarToolbarButton
            icon={<List size={14} />}
            label="Outline"
            active={sidebarView === 'outline'}
            pressed={sidebarView === 'outline'}
            testId="sections-sidebar-view-outline"
            onClick={() => setSidebarView('outline')}
          />
        </SidebarToolbar>
      </div>

      {sidebarView === 'outline' ? (
        outline?.html ? (
          <SectionsSidebarFilmstrip
            outline={outline}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorderOpenDocument?.(fromIndex, toIndex)}
          />
        ) : (
          <p className="px-3 py-4 text-xs text-muted-foreground" data-testid="documents-outline-empty">
            {sectionsFilmstripEmptyCopy(Boolean(outline))}
          </p>
        )
      ) : (
        <>
          <SidebarNewItem
            label="New document"
            title="New document"
            onClick={() =>
              createDocument(
                templates.length > 0 ? resolveDocumentsTemplateId(templates) : undefined,
              )
            }
            disabled={creating}
            menuLabel="Choose a template"
            menuOptions={templateOptions}
            menuOpen={templateMenuOpen}
            onMenuOpenChange={setTemplateMenuOpen}
          />

          {actionError ? <p className="px-2 pb-1 text-xs text-red-600">{actionError}</p> : null}

          <SectionsTreeView
            documents={documents}
            rootHref={sectionsBase}
            currentPath={pathname}
            rootExpanded={rootExpanded}
            onToggleRoot={() => setRootExpanded((open) => !open)}
            expandedDocuments={expandedDocuments}
            onToggleDocument={(slug) =>
              setExpandedDocuments((current) =>
                current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
              )
            }
            expandedDirs={expandedDirs}
            onToggleDir={(path) =>
              setExpandedDirs((current) =>
                current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
              )
            }
            onOpenDocument={(document) => {
              setSelectedSlug(document.slug);
              setSelectedTitle(document.label);
              openDocumentsAgentPane({ slug: document.slug, title: document.label });
            }}
            renamingSlug={renamingSlug}
            onStartRename={(slug) => setRenamingSlug(slug)}
            onRename={(slug, title) => {
              void renameDocument(slug, title);
              setRenamingSlug(null);
            }}
            onCancelRename={() => setRenamingSlug(null)}
            onArchive={(slug) => void archiveDocument(slug, true)}
          />

          {archived.length > 0 ? (
            <div className="chat-section-group">
              <button
                type="button"
                data-testid="sections-archived-toggle"
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
                <SectionsTreeView
                  documents={archivedDocuments}
                  rootHref={sectionsBase}
                  currentPath={pathname}
                  rootExpanded
                  onToggleRoot={() => {}}
                  hideRoot
                  emptyLabel="No archived documents"
                  expandedDocuments={expandedDocuments}
                  onToggleDocument={(slug) =>
                    setExpandedDocuments((current) =>
                      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
                    )
                  }
                  expandedDirs={expandedDirs}
                  onToggleDir={(path) =>
                    setExpandedDirs((current) =>
                      current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
                    )
                  }
                  onOpenDocument={(document) => {
                    setSelectedSlug(document.slug);
                    setSelectedTitle(document.label);
                    openDocumentsAgentPane({ slug: document.slug, title: document.label });
                  }}
                  renamingSlug={renamingSlug}
                  onStartRename={(slug) => setRenamingSlug(slug)}
                  onRename={(slug, title) => {
                    void renameDocument(slug, title);
                    setRenamingSlug(null);
                  }}
                  onCancelRename={() => setRenamingSlug(null)}
                  onArchive={(slug) => void archiveDocument(slug, false)}
                />
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </CollapsibleSection>
  );
}

function SectionsSidebarFilmstrip({
  outline,
  selectedIndex,
  onSelect,
  onReorder,
}: {
  outline: DocumentsOutlineDocument;
  selectedIndex: number;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const sections = parseDocumentsOutline(outline.html);
  return (
    <DocumentsOutline
      html={outline.html}
      workspaceId={outline.workspaceId}
      slug={outline.slug}
      sections={sections}
      selectedIndex={clampSectionIndex(selectedIndex, sections.length)}
      disabled={outline.disabled}
      onSelect={onSelect}
      onReorder={onReorder}
    />
  );
}
