'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { ChevronRight, FolderTree, LayoutGrid, Table2 } from 'lucide-react';
import {
  DEFAULT_SHEETS_TEMPLATE_ID,
  openSheetsAgentPane,
  sheetsApiErrorMessage,
  startNewWorkbook,
} from '@/lib/create-sheets-project';
import { partitionSheetsProjects, patchSheetsProject } from '@/lib/sheets-project-actions';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import {
  sheetsTemplateMenuRows,
  type SheetsSeedTemplate,
} from '@/lib/sheets-templates';
import { authFetch } from '@/stores/auth';
import {
  SHEETS_DECK_UPDATED_EVENT,
  useSheetsStore,
  type SheetsFilmstripWorkbook,
  type SheetsProject,
} from '@/stores/sheets';
import { SheetsFilmstrip } from '@/components/sheets/sheets-filmstrip';
import { clampTabIndex, parseWorkbookTabs } from '@/components/sheets/sheets-outline';
import { CollapsibleSection } from './collapsible-section';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';
import { SidebarToolbar, SidebarToolbarButton } from './sidebar-toolbar';
import {
  buildSheetsTree,
  initialExpandedSheetsWorkbooks,
  type SheetsProjectTree,
} from './sheets-tree';
import { SheetsTreeView } from './sheets-tree-view';
import { sheetsFilmstripEmptyCopy } from './sheets-section-views';
import { getWorkspacePath } from './utils';

/**
 * Sheets sidebar: Ontology-style view toolbar, then Sheets or Filmstrip.
 *
 * Sheets is the file tree. Filmstrip is vertical thumbs for the open workbook.
 * Templates hang off the New workbook caret on the Sheets view.
 */
export function SheetsSection({
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
  const sheetsBase = getWorkspacePath(workspaceId, '/sheets');
  const [projects, setProjects] = useState<SheetsProject[]>([]);
  const [templates, setTemplates] = useState<SheetsSeedTemplate[]>([]);
  const [trees, setTrees] = useState<Record<string, SheetsProjectTree>>({});
  const [rootExpanded, setRootExpanded] = useState(true);
  const [expandedWorkbooks, setExpandedWorkbooks] = useState<string[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [renamingSlug, setRenamingSlug] = useState<string | null>(null);
  const selectedSlug = useSheetsStore((s) => s.selectedSlug);
  const selectedTitle = useSheetsStore((s) => s.selectedTitle);
  const setSelectedSlug = useSheetsStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSheetsStore((s) => s.setSelectedTitle);
  const sidebarView = useSheetsStore((s) => s.sidebarView);
  const setSidebarView = useSheetsStore((s) => s.setSidebarView);
  const selectedIndex = useSheetsStore((s) => s.selectedIndex);
  const setSelectedIndex = useSheetsStore((s) => s.setSelectedIndex);
  const filmstrip = useSheetsStore((s) => s.filmstrip);
  const reorderOpenWorkbook = useSheetsStore((s) => s.reorderOpenWorkbook);

  const openSlug = routeSlug || selectedSlug;

  const fetchProjects = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/sheets/projects?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (res.ok) setProjects((await res.json()) as SheetsProject[]);
    } catch {
      // ignore
    }
  }, [workspaceId]);

  const fetchTemplates = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/sheets/templates?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) return;
      const body = (await res.json()) as SheetsSeedTemplate[];
      setTemplates(
        body.map((row) => ({
          ...row,
          sheets: row.sheets ?? [],
          assets: row.assets ?? [],
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId]);

  /** A workbook's own files, fetched when its folder opens. */
  const fetchTree = useCallback(
    async (slug: string) => {
      if (!workspaceId || !slug) return;
      try {
        const res = await authFetch(
          `/api/sheets/projects/${encodeURIComponent(slug)}/tree` +
            `?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) return;
        const body = (await res.json()) as SheetsProjectTree;
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

  // Abi names a still-untitled workbook on its first write, so the tree label
  // has to come back from the server instead of waiting for the next navigation.
  // The same write can add a file, so the open workbook's tree is refetched too.
  useEffect(() => {
    const onUpdated = (event: Event) => {
      void fetchProjects();
      const slug =
        (event as CustomEvent<{ slug?: string }>).detail?.slug || openSlug || '';
      if (slug) void fetchTree(slug);
    };
    window.addEventListener(SHEETS_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SHEETS_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchProjects, fetchTree, openSlug]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  // The workbook being edited starts open, the way an editor reveals the file it
  // has loaded.
  useEffect(() => {
    if (!openSlug) return;
    setExpandedWorkbooks((current) =>
      current.includes(openSlug)
        ? current
        : [...current, ...initialExpandedSheetsWorkbooks(openSlug)],
    );
  }, [openSlug]);

  useEffect(() => {
    for (const slug of expandedWorkbooks) {
      if (!trees[slug]) void fetchTree(slug);
    }
  }, [expandedWorkbooks, trees, fetchTree]);

  const { active, archived } = useMemo(() => partitionSheetsProjects(projects), [projects]);
  const openIsArchived = Boolean(openSlug && archived.some((row) => row.slug === openSlug));

  const workbooks = useMemo(
    () =>
      buildSheetsTree(active, {
        workspaceId,
        openSlug: openIsArchived ? null : openSlug,
        openTitle: openIsArchived ? null : selectedTitle,
        trees,
      }),
    [active, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const archivedWorkbooks = useMemo(
    () =>
      buildSheetsTree(archived, {
        workspaceId,
        openSlug: openIsArchived ? openSlug : null,
        openTitle: openIsArchived ? selectedTitle : null,
        trees,
      }),
    [archived, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const renameWorkbook = useCallback(
    async (slug: string, title: string) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, title } : row)),
      );
      if (selectedSlug === slug) setSelectedTitle(title);
      try {
        await patchSheetsProject(workspaceId, slug, { title });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, selectedSlug, setSelectedTitle, fetchProjects],
  );

  const archiveWorkbook = useCallback(
    async (slug: string, archivedFlag: boolean) => {
      setProjects((current) =>
        current.map((row) => (row.slug === slug ? { ...row, archived: archivedFlag } : row)),
      );
      try {
        await patchSheetsProject(workspaceId, slug, { archived: archivedFlag });
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [workspaceId, fetchProjects],
  );

  const createWorkbook = useCallback(
    (templateId: string) => {
      if (!workspaceId || creating) return;
      setCreating(true);
      setActionError(null);
      void startNewWorkbook(workspaceId, (href) => router.push(href), templateId)
        .then(() => {
          void fetchProjects();
        })
        .catch((e) => {
          setActionError(
            sheetsApiErrorMessage((e as Error).message, 'Could not create the workbook.'),
          );
        })
        .finally(() => {
          setCreating(false);
        });
    },
    [workspaceId, creating, router, fetchProjects],
  );

  const templateOptions: SidebarNewItemMenuOption[] = sheetsTemplateMenuRows(templates).map(
    (row) =>
      row.kind === 'heading'
        ? { id: row.id, label: row.label, heading: true }
        : {
            id: row.id,
            label: row.label,
            swatch: row.swatch,
            onSelect: () => createWorkbook(row.id),
          },
  );

  return (
    <CollapsibleSection
      id="sheets"
      icon={<Table2 size={18} />}
      label="Sheets"
      description="Spreadsheets in this workspace"
      href={sheetsBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div data-testid="sheets-sidebar-views">
        <SidebarToolbar>
          <SidebarToolbarButton
            icon={<FolderTree size={14} />}
            label="Sheets"
            active={sidebarView === 'sheets'}
            pressed={sidebarView === 'sheets'}
            testId="sheets-sidebar-view-sheets"
            onClick={() => setSidebarView('sheets')}
          />
          <SidebarToolbarButton
            icon={<LayoutGrid size={14} />}
            label="Filmstrip"
            active={sidebarView === 'filmstrip'}
            pressed={sidebarView === 'filmstrip'}
            testId="sheets-sidebar-view-filmstrip"
            onClick={() => setSidebarView('filmstrip')}
          />
        </SidebarToolbar>
      </div>

      {sidebarView === 'filmstrip' ? (
        filmstrip?.html ? (
          <SheetsSidebarFilmstrip
            filmstrip={filmstrip}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorderOpenWorkbook?.(fromIndex, toIndex)}
          />
        ) : (
          <p className="px-3 py-4 text-xs text-muted-foreground" data-testid="sheets-filmstrip-empty">
            {sheetsFilmstripEmptyCopy(Boolean(filmstrip))}
          </p>
        )
      ) : (
        <>
          <SidebarNewItem
            label="New workbook"
            title="New workbook"
            onClick={() => createWorkbook(DEFAULT_SHEETS_TEMPLATE_ID)}
            disabled={creating}
            menuLabel="Choose a template"
            menuOptions={templateOptions}
            menuOpen={templateMenuOpen}
            onMenuOpenChange={setTemplateMenuOpen}
          />

          {actionError ? <p className="px-2 pb-1 text-xs text-red-600">{actionError}</p> : null}

          <SheetsTreeView
            workbooks={workbooks}
            rootHref={sheetsBase}
            currentPath={pathname}
            rootExpanded={rootExpanded}
            onToggleRoot={() => setRootExpanded((open) => !open)}
            expandedWorkbooks={expandedWorkbooks}
            onToggleWorkbook={(slug) =>
              setExpandedWorkbooks((current) =>
                current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
              )
            }
            expandedDirs={expandedDirs}
            onToggleDir={(path) =>
              setExpandedDirs((current) =>
                current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
              )
            }
            onOpenWorkbook={(workbook) => {
              setSelectedSlug(workbook.slug);
              setSelectedTitle(workbook.label);
              openSheetsAgentPane({ slug: workbook.slug, title: workbook.label });
            }}
            renamingSlug={renamingSlug}
            onStartRename={(slug) => setRenamingSlug(slug)}
            onRename={(slug, title) => {
              void renameWorkbook(slug, title);
              setRenamingSlug(null);
            }}
            onCancelRename={() => setRenamingSlug(null)}
            onArchive={(slug) => void archiveWorkbook(slug, true)}
          />

          {archived.length > 0 ? (
            <div className="chat-section-group">
              <button
                type="button"
                data-testid="sheets-archived-toggle"
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
                <SheetsTreeView
                  workbooks={archivedWorkbooks}
                  rootHref={sheetsBase}
                  currentPath={pathname}
                  rootExpanded
                  onToggleRoot={() => {}}
                  hideRoot
                  emptyLabel="No archived workbooks"
                  expandedWorkbooks={expandedWorkbooks}
                  onToggleWorkbook={(slug) =>
                    setExpandedWorkbooks((current) =>
                      current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug],
                    )
                  }
                  expandedDirs={expandedDirs}
                  onToggleDir={(path) =>
                    setExpandedDirs((current) =>
                      current.includes(path) ? current.filter((p) => p !== path) : [...current, path],
                    )
                  }
                  onOpenWorkbook={(workbook) => {
                    setSelectedSlug(workbook.slug);
                    setSelectedTitle(workbook.label);
                    openSheetsAgentPane({ slug: workbook.slug, title: workbook.label });
                  }}
                  renamingSlug={renamingSlug}
                  onStartRename={(slug) => setRenamingSlug(slug)}
                  onRename={(slug, title) => {
                    void renameWorkbook(slug, title);
                    setRenamingSlug(null);
                  }}
                  onCancelRename={() => setRenamingSlug(null)}
                  onArchive={(slug) => void archiveWorkbook(slug, false)}
                />
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </CollapsibleSection>
  );
}

function SheetsSidebarFilmstrip({
  filmstrip,
  selectedIndex,
  onSelect,
  onReorder,
}: {
  filmstrip: SheetsFilmstripWorkbook;
  selectedIndex: number;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const tabs = parseWorkbookTabs(filmstrip.html);
  return (
    <SheetsFilmstrip
      html={filmstrip.html}
      workspaceId={filmstrip.workspaceId}
      slug={filmstrip.slug}
      tabs={tabs}
      selectedIndex={clampTabIndex(selectedIndex, tabs.length)}
      disabled={filmstrip.disabled}
      onSelect={onSelect}
      onReorder={onReorder}
    />
  );
}
