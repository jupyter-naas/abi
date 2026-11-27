'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { ChevronRight, FolderTree } from 'lucide-react';
import { pushOfficeCreate, useOfficeCreateStore } from '@/components/office/office-create-state';
import type { OfficeCreateKind } from '@/components/office/office-create';
import type { OfficeKind } from '@/components/office/office-kinds';
import { OFFICE_TEMPLATE_CATALOGS } from '@/components/office/office-templates';
import { withOfficeListRetry } from '@/lib/office-list-retry';
import { authFetch } from '@/stores/auth';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import { CollapsibleSection } from './collapsible-section';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';
import { SidebarToolbar, SidebarToolbarButton } from './sidebar-toolbar';
import { buildOfficeTree, initialExpandedItems, type OfficeProjectTree } from './office-tree';
import { OfficeTreeView, type OfficeTreeViewProps } from './office-tree-view';
import { getWorkspacePath } from './utils';

/** The selection and view fields every office store carries. */
export type OfficeSidebarState<V extends string> = {
  selectedSlug: string | null;
  selectedTitle: string | null;
  sidebarView: V;
  setSelectedSlug: (slug: string | null) => void;
  setSelectedTitle: (title: string | null) => void;
  setSidebarView: (view: V) => void;
};

type Project = { slug: string; title: string; archived?: boolean };
type SeedTemplate = { id: string; name: string } & Record<string, unknown>;

export type OfficeSectionConfig<V extends string> = {
  kind: OfficeKind;
  useStore: <U>(selector: (state: OfficeSidebarState<V>) => U) => U;
  /** Window event the kind dispatches when Abi or another client writes an item. */
  updatedEvent: string;
  /** The sidebar's two views: the file tree, and the open item's parts. */
  views: {
    tree: { id: V; label: string };
    detail: { id: V; label: string; icon: ReactNode; loading: string; empty: string };
  };
  /** Section title and its hover description. */
  label: string;
  description: string;
  newItem: { label: string; title: string };
  /**
   * How New runs: through the shared create overlay, or the kind's own starter
   * (which navigates itself and reports errors here).
   */
  create:
    | { overlay: OfficeCreateKind }
    | {
        start: (workspaceId: string, navigate: (href: string) => void, templateId: string) => Promise<unknown>;
        errorMessage: (message: string) => string;
      };
  patch: (workspaceId: string, slug: string, patch: { title?: string; archived?: boolean }) => Promise<unknown>;
  openAgentPane: (opts: { slug: string; title: string }) => void;
  /**
   * List recovery (Documents first): retry the list on 5xx/429, refetch on focus and
   * online, clear it on navigation, and take a new title straight from the update event.
   */
  recoverList?: boolean;
};

/** Empty-line copy of the detail view: never claims to load when nothing is open. */
export function officeDetailEmptyCopy(
  detail: { loading: string; empty: string },
  hasOpenSession: boolean,
): string {
  return hasOpenSession ? detail.loading : detail.empty;
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Fetch JSON for a sidebar list; with recovery, 5xx/429 throw so the retry runs. */
async function fetchList<T>(url: string, recover: boolean): Promise<T | null> {
  const run = async () => {
    const res = await authFetch(url);
    if (!res.ok) {
      if (recover && (res.status >= 500 || res.status === 429)) throw new Error(`Failed (${res.status})`);
      return null;
    }
    return (await res.json()) as T;
  };
  return recover ? withOfficeListRetry(run) : run();
}

/**
 * Documents, Sheets or Slides sidebar: Ontology-style view toolbar, then the file
 * tree or the open item's parts (outline, filmstrip). Templates hang off the New
 * caret on the tree view.
 */
export function OfficeSection<V extends string>({
  config,
  collapsed,
  detailOnly,
  hasOpenSession,
  renderDetail,
}: {
  config: OfficeSectionConfig<V>;
  collapsed: boolean;
  detailOnly?: boolean;
  /** An item is open in the pane (its outline or filmstrip may still be loading). */
  hasOpenSession: boolean;
  /** The detail view's content, or null while there is nothing to show. */
  renderDetail: () => ReactNode;
}) {
  const { kind, useStore, views, recoverList = false } = config;
  const catalog = OFFICE_TEMPLATE_CATALOGS[kind.id];
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const routeSlug = typeof params?.slug === 'string' ? params.slug : '';
  const base = getWorkspacePath(workspaceId, `/${kind.id}`);
  const [projects, setProjects] = useState<Project[]>([]);
  const [templates, setTemplates] = useState<SeedTemplate[]>([]);
  const [trees, setTrees] = useState<Record<string, OfficeProjectTree>>({});
  const [rootExpanded, setRootExpanded] = useState(true);
  const [expandedItems, setExpandedItems] = useState<string[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const overlayKind = 'overlay' in config.create ? config.create.overlay : null;
  const overlayCreating = useOfficeCreateStore((s) => overlayKind !== null && s.kind === overlayKind);
  const [startCreating, setStartCreating] = useState(false);
  const creating = overlayCreating || startCreating;
  const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [renamingSlug, setRenamingSlug] = useState<string | null>(null);
  const selectedSlug = useStore((s) => s.selectedSlug);
  const selectedTitle = useStore((s) => s.selectedTitle);
  const setSelectedSlug = useStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useStore((s) => s.setSelectedTitle);
  const sidebarView = useStore((s) => s.sidebarView);
  const setSidebarView = useStore((s) => s.setSidebarView);

  const openSlug = routeSlug || selectedSlug;
  const query = `workspace_id=${encodeURIComponent(workspaceId)}`;

  const fetchProjects = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const rows = await fetchList<Project[]>(`/api/${kind.id}/projects?${query}`, recoverList);
      if (rows) setProjects(rows);
    } catch {
      // Recovery retries on focus / online / next navigation.
    }
  }, [workspaceId, kind.id, query, recoverList]);

  const fetchTemplates = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const rows = await fetchList<SeedTemplate[]>(`/api/${kind.id}/templates?${query}`, recoverList);
      if (!rows) return;
      setTemplates(
        rows.map((row) => ({
          ...row,
          [kind.templateParts]: row[kind.templateParts] ?? [],
          assets: row.assets ?? [],
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId, kind.id, kind.templateParts, query, recoverList]);

  /** An item's own files, fetched when its folder opens. */
  const fetchTree = useCallback(
    async (slug: string) => {
      if (!workspaceId || !slug) return;
      try {
        const res = await authFetch(`/api/${kind.id}/projects/${encodeURIComponent(slug)}/tree?${query}`);
        if (!res.ok) return;
        const body = (await res.json()) as OfficeProjectTree;
        setTrees((current) => ({ ...current, [slug]: body }));
      } catch {
        // ignore
      }
    },
    [workspaceId, kind.id, query],
  );

  useEffect(() => {
    if (recoverList) setProjects([]);
    void fetchProjects();
    void fetchTemplates();
  }, [fetchProjects, fetchTemplates, pathname, recoverList]);

  useEffect(() => {
    if (!recoverList) return;
    const refresh = () => {
      void fetchProjects();
      void fetchTemplates();
    };
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      window.removeEventListener('online', refresh);
    };
  }, [fetchProjects, fetchTemplates, recoverList]);

  // Abi names a still-untitled item on its first write, so the tree label has to
  // come back from the server instead of waiting for the next navigation. The same
  // write can add a file, so the open item's tree is refetched too.
  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ slug?: string; title?: string }>).detail;
      const slug = detail?.slug || openSlug || '';
      const title = recoverList ? (detail?.title || '').trim() : '';
      if (title && slug) {
        setProjects((current) => current.map((row) => (row.slug === slug ? { ...row, title } : row)));
        if (selectedSlug === slug || openSlug === slug) setSelectedTitle(title);
      }
      void fetchProjects();
      if (slug) void fetchTree(slug);
    };
    window.addEventListener(config.updatedEvent, onUpdated);
    return () => window.removeEventListener(config.updatedEvent, onUpdated);
  }, [config.updatedEvent, fetchProjects, fetchTree, openSlug, selectedSlug, setSelectedTitle, recoverList]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  // The item being edited starts open, the way an editor reveals the file it has loaded.
  useEffect(() => {
    if (!openSlug) return;
    setExpandedItems((current) =>
      current.includes(openSlug) ? current : [...current, ...initialExpandedItems(openSlug)],
    );
  }, [openSlug]);

  useEffect(() => {
    for (const slug of expandedItems) {
      if (!trees[slug]) void fetchTree(slug);
    }
  }, [expandedItems, trees, fetchTree]);

  const { active, archived } = useMemo(() => {
    const listed = projects.filter((project) => project?.slug);
    return {
      active: listed.filter((project) => !project.archived),
      archived: listed.filter((project) => project.archived),
    };
  }, [projects]);
  const openIsArchived = Boolean(openSlug && archived.some((row) => row.slug === openSlug));

  const items = useMemo(
    () =>
      buildOfficeTree(kind, active, {
        workspaceId,
        openSlug: openIsArchived ? null : openSlug,
        openTitle: openIsArchived ? null : selectedTitle,
        trees,
      }),
    [kind, active, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const archivedItems = useMemo(
    () =>
      buildOfficeTree(kind, archived, {
        workspaceId,
        openSlug: openIsArchived ? openSlug : null,
        openTitle: openIsArchived ? selectedTitle : null,
        trees,
      }),
    [kind, archived, workspaceId, openSlug, openIsArchived, selectedTitle, trees],
  );

  const patchProject = useCallback(
    async (slug: string, patch: { title?: string; archived?: boolean }) => {
      setProjects((current) => current.map((row) => (row.slug === slug ? { ...row, ...patch } : row)));
      if (patch.title && selectedSlug === slug) setSelectedTitle(patch.title);
      try {
        await config.patch(workspaceId, slug, patch);
      } catch (e) {
        setActionError((e as Error).message);
        void fetchProjects();
      }
    },
    [config, workspaceId, selectedSlug, setSelectedTitle, fetchProjects],
  );

  const createItem = useCallback(
    (templateId?: string) => {
      const { create } = config;
      if ('overlay' in create) {
        setActionError(null);
        pushOfficeCreate(router, create.overlay, workspaceId, templateId);
        return;
      }
      if (!workspaceId || creating || !templateId) return;
      setStartCreating(true);
      setActionError(null);
      void create
        .start(workspaceId, (href) => router.push(href), templateId)
        .then(() => void fetchProjects())
        .catch((e) => setActionError(create.errorMessage((e as Error).message)))
        .finally(() => setStartCreating(false));
    },
    [config, workspaceId, creating, router, fetchProjects],
  );

  const templateOptions: SidebarNewItemMenuOption[] = catalog.menuRows(templates).map((row) =>
    row.kind === 'heading'
      ? { id: row.id, label: row.label, heading: true }
      : { id: row.id, label: row.label, swatch: row.swatch, onSelect: () => createItem(row.id) },
  );

  const treeProps: Omit<OfficeTreeViewProps, 'items' | 'rootExpanded' | 'onToggleRoot' | 'onArchive'> = {
    kind,
    rootHref: base,
    currentPath: pathname,
    expandedItems,
    onToggleItem: (slug) => setExpandedItems((current) => toggle(current, slug)),
    expandedDirs,
    onToggleDir: (path) => setExpandedDirs((current) => toggle(current, path)),
    onOpenItem: (item) => {
      setSelectedSlug(item.slug);
      setSelectedTitle(item.label);
      config.openAgentPane({ slug: item.slug, title: item.label });
    },
    renamingSlug,
    onStartRename: (slug) => setRenamingSlug(slug),
    onRename: (slug, title) => {
      void patchProject(slug, { title });
      setRenamingSlug(null);
    },
    onCancelRename: () => setRenamingSlug(null),
  };

  const SectionIcon = kind.icon;
  const prefix = kind.testIdPrefix;
  const detail = sidebarView === views.detail.id ? renderDetail() : null;

  return (
    <CollapsibleSection
      id={kind.id}
      icon={<SectionIcon size={18} />}
      label={config.label}
      description={config.description}
      href={base}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div data-testid={`${prefix}-sidebar-views`}>
        <SidebarToolbar>
          {[
            { ...views.tree, icon: <FolderTree size={14} /> },
            views.detail,
          ].map((view) => (
            <SidebarToolbarButton
              key={view.id}
              icon={view.icon}
              label={view.label}
              active={sidebarView === view.id}
              pressed={sidebarView === view.id}
              testId={`${prefix}-sidebar-view-${view.id}`}
              onClick={() => setSidebarView(view.id)}
            />
          ))}
        </SidebarToolbar>
      </div>

      {sidebarView === views.detail.id ? (
        detail ?? (
          <p className="px-3 py-4 text-xs text-muted-foreground" data-testid={`${kind.id}-${views.detail.id}-empty`}>
            {officeDetailEmptyCopy(views.detail, hasOpenSession)}
          </p>
        )
      ) : (
        <>
          <SidebarNewItem
            label={config.newItem.label}
            title={config.newItem.title}
            onClick={() => createItem(catalog.defaultTemplateId(templates))}
            disabled={creating}
            menuLabel="Choose a template"
            menuOptions={templateOptions}
            menuOpen={templateMenuOpen}
            onMenuOpenChange={setTemplateMenuOpen}
          />

          {actionError ? <p className="px-2 pb-1 text-xs text-red-600">{actionError}</p> : null}

          <OfficeTreeView
            {...treeProps}
            items={items}
            rootExpanded={rootExpanded}
            onToggleRoot={() => setRootExpanded((open) => !open)}
            onArchive={(slug) => void patchProject(slug, { archived: true })}
          />

          {archived.length > 0 ? (
            <div className="chat-section-group">
              <button
                type="button"
                data-testid={`${prefix}-archived-toggle`}
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
                <OfficeTreeView
                  {...treeProps}
                  items={archivedItems}
                  rootExpanded
                  onToggleRoot={() => {}}
                  hideRoot
                  emptyLabel={kind.archivedEmptyLabel}
                  onArchive={(slug) => void patchProject(slug, { archived: false })}
                />
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </CollapsibleSection>
  );
}
