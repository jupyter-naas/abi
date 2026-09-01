'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { Presentation } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  applySlidesTemplate,
  renameSlidesProject,
  sanitizeSlidesTitle,
  slidesApiErrorMessage,
  startNewPresentation,
} from '@/lib/create-slides-project';
import {
  buildSlidesExplorer,
  defaultExpandedIds,
  type SlidesExplorerNode,
  type SlidesProjectTree,
} from '@/lib/slides-explorer';
import type { SlidesSeedTemplate } from '@/lib/slides-templates';
import { authFetch } from '@/stores/auth';
import {
  SLIDES_DECK_UPDATED_EVENT,
  useSlidesStore,
  type SlidesDeckUpdatedDetail,
  type SlidesProject,
} from '@/stores/slides';
import { CollapsibleSection } from './collapsible-section';
import { SlidesExplorerTree } from './slides-explorer-tree';
import { getWorkspacePath } from './utils';

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
  const [tree, setTree] = useState<SlidesProjectTree | null>(null);
  const [expandedIds, setExpandedIds] = useState<string[]>(defaultExpandedIds());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [assetPreview, setAssetPreview] = useState<{ name: string; src: string } | null>(null);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const selectedTitle = useSlidesStore((s) => s.selectedTitle);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSlidesStore((s) => s.setSelectedTitle);
  const deckDirty = useSlidesStore((s) => s.deckDirty);
  const refreshToken = useSlidesStore((s) => s.refreshToken);

  const persistedOpen =
    selectedSlug && projects.some((p) => p.slug === selectedSlug) ? selectedSlug : null;
  const openSlug = routeSlug || persistedOpen;
  const openProject = projects.find((p) => p.slug === openSlug) ?? null;

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
          files: row.files?.length ? row.files : [{ name: 'deck.html', kind: 'html' }],
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId]);

  const fetchTree = useCallback(async () => {
    if (!workspaceId || !openSlug) {
      setTree(null);
      return;
    }
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(openSlug)}/tree?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
        { cache: 'no-store' },
      );
      if (!res.ok) {
        setTree(null);
        return;
      }
      setTree((await res.json()) as SlidesProjectTree);
    } catch {
      setTree(null);
    }
  }, [workspaceId, openSlug]);

  useEffect(() => {
    void fetchProjects();
    void fetchTemplates();
  }, [fetchProjects, fetchTemplates, pathname]);

  useEffect(() => {
    void fetchTree();
  }, [fetchTree, refreshToken, pathname]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<SlidesDeckUpdatedDetail>).detail;
      if (detail?.slug && openSlug && detail.slug !== openSlug) return;
      void fetchProjects();
      void fetchTree();
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [fetchProjects, fetchTree, openSlug]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  useEffect(() => {
    if (!openSlug) return;
    setExpandedIds((current) => {
      const extra = defaultExpandedIds(openSlug);
      const missing = extra.filter((id) => !current.includes(id));
      return missing.length ? [...current, ...missing] : current;
    });
  }, [openSlug]);

  const folderLabel = openProject?.title || selectedTitle || openSlug || 'Presentation';

  const explorer = useMemo(
    () =>
      buildSlidesExplorer({
        projectTitle: folderLabel,
        projectSlug: openSlug,
        projectRoot: tree?.root || openProject?.deck_path?.replace(/\/deck\.html$/, '') || null,
        tree,
        templates,
        projects,
      }),
    [folderLabel, openSlug, openProject?.deck_path, tree, templates, projects],
  );

  const toggleNode = (id: string) => {
    setExpandedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const createNew = () => {
    if (!workspaceId || creating) return;
    setCreating(true);
    setActionError(null);
    void startNewPresentation(workspaceId, (href) => router.push(href))
      .then((created) => {
        void fetchProjects();
        setSelectedId(`project:${created.slug}`);
        setRenamingId(`project:${created.slug}`);
        setExpandedIds((current) => [
          ...new Set([...current, ...defaultExpandedIds(created.slug)]),
        ]);
      })
      .catch((e) => {
        setActionError(slidesApiErrorMessage((e as Error).message, 'Could not create the deck.'));
      })
      .finally(() => {
        setCreating(false);
      });
  };

  const commitRename = (node: SlidesExplorerNode, nextName: string) => {
    const title = sanitizeSlidesTitle(nextName);
    setRenamingId(null);
    if (!workspaceId || !node.slug || !node.renamable) return;
    if (!title || title === node.name) return;
    setActionError(null);
    void renameSlidesProject(workspaceId, node.slug, title)
      .then((updated) => {
        setProjects((current) =>
          current.map((row) =>
            row.slug === updated.slug ? { ...row, title: updated.title } : row,
          ),
        );
        if (openSlug === updated.slug) {
          setSelectedTitle(updated.title);
        }
      })
      .catch((e) => {
        setActionError(slidesApiErrorMessage((e as Error).message, 'Could not rename the deck.'));
      });
  };

  const applyTemplate = (templateId: string) => {
    const template = templates.find((row) => row.id === templateId);
    if (!template || !workspaceId || creating || applyingId) return;
    if (openSlug && deckDirty) {
      const ok = window.confirm(
        'Replace the open deck with this template? Unsaved edits will be lost.',
      );
      if (!ok) return;
    }
    setApplyingId(template.id);
    setActionError(null);
    void applySlidesTemplate(workspaceId, template.id, openSlug || null, (href) => router.push(href))
      .then(() => {
        void fetchProjects();
        void fetchTree();
      })
      .catch((e) => {
        setActionError(slidesApiErrorMessage((e as Error).message, 'Could not apply the template.'));
      })
      .finally(() => {
        setApplyingId(null);
      });
  };

  const previewAsset = (node: SlidesExplorerNode) => {
    if (!workspaceId || !openSlug || node.templateId || !node.slug) {
      setAssetPreview(null);
      return;
    }
    void authFetch(
      `/api/slides/projects/${encodeURIComponent(openSlug)}/assets/${encodeURIComponent(node.name)}?workspace_id=${encodeURIComponent(workspaceId)}`,
    )
      .then(async (res) => {
        if (!res.ok) {
          setAssetPreview(null);
          return;
        }
        const body = (await res.json()) as { content?: string };
        const content = body.content || '';
        if (content.startsWith('data:image/')) {
          setAssetPreview({ name: node.name, src: content });
          return;
        }
        if (content.includes('<svg')) {
          setAssetPreview({
            name: node.name,
            src: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(content)}`,
          });
          return;
        }
        setAssetPreview(null);
      })
      .catch(() => {
        setAssetPreview(null);
      });
  };

  const activate = (node: SlidesExplorerNode) => {
    setSelectedId(node.id);
    if (node.kind === 'folder' && node.action === 'noop') {
      toggleNode(node.id);
      return;
    }
    if (node.action === 'apply-template' && node.templateId) {
      applyTemplate(node.templateId);
      return;
    }
    if (node.action === 'open-deck' && openSlug) {
      setSelectedSlug(openSlug);
      router.push(`${slidesBase}/${openSlug}`);
      return;
    }
    if (node.action === 'open-project' && node.slug) {
      setSelectedSlug(node.slug);
      router.push(`${slidesBase}/${node.slug}`);
      return;
    }
    if (node.action === 'select-asset') {
      previewAsset(node);
    }
  };

  return (
    <CollapsibleSection
      id="slides"
      icon={<Presentation size={18} />}
      label="Slides"
      description="Presentation files"
      href={slidesBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onAdd={createNew}
    >
      <div className="flex items-center justify-between px-1 pb-1">
        <button
          type="button"
          onClick={() => router.push(slidesBase)}
          className={cn(
            'rounded-md px-2 py-1 text-xs font-medium hover:bg-workspace-accent-10',
            pathname === slidesBase && 'text-workspace-accent',
          )}
        >
          All projects
        </button>
        <button
          type="button"
          onClick={createNew}
          disabled={creating}
          title="New"
          aria-label="New"
          className="rounded px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent disabled:opacity-50"
        >
          New
        </button>
      </div>
      {actionError ? <p className="px-3 pb-1 text-xs text-red-600">{actionError}</p> : null}
      {applyingId ? (
        <p className="px-3 pb-1 text-[10px] text-muted-foreground">Applying template…</p>
      ) : null}

      <div className="px-1 pb-1">
        <SlidesExplorerTree
          nodes={explorer}
          expandedIds={expandedIds}
          selectedId={selectedId}
          renamingId={renamingId}
          onToggle={toggleNode}
          onActivate={activate}
          onStartRename={(node) => {
            if (!node.renamable) return;
            setSelectedId(node.id);
            setRenamingId(node.id);
          }}
          onCommitRename={commitRename}
          onCancelRename={() => setRenamingId(null)}
        />
      </div>

      {assetPreview ? (
        <div className="mx-2 mb-2 rounded-md border border-border/60 bg-muted/30 p-2">
          <div className="truncate text-[10px] text-muted-foreground">{assetPreview.name}</div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={assetPreview.src}
            alt=""
            className="mt-1 max-h-16 max-w-full rounded object-contain"
          />
        </div>
      ) : null}
    </CollapsibleSection>
  );
}
