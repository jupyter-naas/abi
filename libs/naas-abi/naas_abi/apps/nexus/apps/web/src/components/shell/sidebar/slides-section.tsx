'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import {
  ChevronRight,
  FileCode2,
  Folder,
  Image as ImageIcon,
  LayoutTemplate,
  Presentation,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  applySlidesTemplate,
  slidesApiErrorMessage,
  startNewPresentation,
} from '@/lib/create-slides-project';
import {
  templateAssetLabel,
  templateSlideLabel,
  type SlidesSeedTemplate,
} from '@/lib/slides-templates';
import { authFetch } from '@/stores/auth';
import { useSlidesStore, type SlidesProject } from '@/stores/slides';
import { CollapsibleSection } from './collapsible-section';
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
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const selectedTitle = useSlidesStore((s) => s.selectedTitle);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);
  const deckDirty = useSlidesStore((s) => s.deckDirty);

  const openSlug = routeSlug || selectedSlug;
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
        })),
      );
    } catch {
      // ignore
    }
  }, [workspaceId]);

  useEffect(() => {
    void fetchProjects();
    void fetchTemplates();
  }, [fetchProjects, fetchTemplates, pathname]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  const folderLabel = openProject?.title || selectedTitle || openSlug || 'Presentation';
  const appliedTemplateId = openProject?.template_id || null;

  const toggleTemplate = (id: string) => {
    setExpandedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const createNew = () => {
    if (!workspaceId || creating) return;
    setCreating(true);
    setActionError(null);
    void startNewPresentation(workspaceId, (href) => router.push(href))
      .catch((e) => {
        setActionError(
          slidesApiErrorMessage((e as Error).message, 'Could not create the deck.'),
        );
      })
      .finally(() => {
        setCreating(false);
      });
  };

  const applyTemplate = (template: SlidesSeedTemplate) => {
    if (!workspaceId || creating || applyingId) return;
    if (openSlug && deckDirty) {
      const ok = window.confirm(
        'Replace the open deck with this template? Unsaved edits will be lost.',
      );
      if (!ok) return;
    }
    setApplyingId(template.id);
    setActionError(null);
    void applySlidesTemplate(workspaceId, template.id, openSlug || null, (href) =>
      router.push(href),
    )
      .then(() => {
        void fetchProjects();
      })
      .catch((e) => {
        setActionError(slidesApiErrorMessage((e as Error).message, 'Could not apply the template.'));
      })
      .finally(() => {
        setApplyingId(null);
      });
  };

  return (
    <CollapsibleSection
      id="slides"
      icon={<Presentation size={18} />}
      label="Slides"
      description="Templates and open deck"
      href={slidesBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="px-1 pb-1">
        <button
          onClick={() => router.push(slidesBase)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium hover:bg-workspace-accent-10',
            pathname === slidesBase && 'text-workspace-accent',
          )}
        >
          All projects
        </button>
      </div>
      {actionError ? <p className="px-3 pb-1 text-xs text-red-600">{actionError}</p> : null}

      {openSlug ? (
        <div className="space-y-0.5 px-1 pb-2">
          <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Open presentation
          </div>
          <button
            type="button"
            onClick={() => {
              setSelectedSlug(openSlug);
              router.push(`${slidesBase}/${openSlug}`);
            }}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-workspace-accent-10',
              pathname.startsWith(`${slidesBase}/${openSlug}`)
                ? 'bg-workspace-accent-10 text-workspace-accent'
                : 'text-foreground',
            )}
          >
            <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{folderLabel}</span>
          </button>
          <div className="ml-3 border-l border-border/60 pl-2">
            <button
              type="button"
              onClick={() => router.push(`${slidesBase}/${openSlug}`)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs font-medium text-workspace-accent hover:bg-workspace-accent-10"
            >
              <FileCode2 size={11} className="flex-shrink-0 text-muted-foreground" />
              <span className="truncate">deck.html</span>
            </button>
          </div>
        </div>
      ) : null}

      <div className="space-y-0.5 px-1">
        <div className="flex items-center justify-between px-2 py-1">
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Templates
          </div>
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
        {templates.length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground">No templates loaded</p>
        ) : (
          templates.map((template) => {
            const expanded = expandedIds.includes(template.id);
            const applying = applyingId === template.id;
            const active = appliedTemplateId === template.id && Boolean(openSlug);
            return (
              <div key={template.id} className="space-y-0.5">
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => toggleTemplate(template.id)}
                    aria-expanded={expanded}
                    aria-label={`Expand ${template.name}`}
                    className="rounded p-1 text-muted-foreground hover:bg-workspace-accent-10 hover:text-foreground"
                  >
                    <ChevronRight
                      size={11}
                      className={cn('transition-transform', expanded && 'rotate-90')}
                    />
                  </button>
                  <button
                    type="button"
                    onClick={() => applyTemplate(template)}
                    disabled={Boolean(applyingId)}
                    title={`Apply ${template.name}`}
                    className={cn(
                      'flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-workspace-accent-10 disabled:opacity-50',
                      active
                        ? 'bg-workspace-accent-10 font-medium text-workspace-accent'
                        : 'text-foreground',
                    )}
                  >
                    <span
                      className="h-2.5 w-2.5 flex-shrink-0 rounded-sm border border-border/70"
                      style={{ background: template.preview_accent || template.preview_bg }}
                      aria-hidden
                    />
                    <LayoutTemplate size={11} className="flex-shrink-0 text-muted-foreground" />
                    <span className="truncate">{template.name}</span>
                    {applying ? (
                      <span className="ml-auto text-[10px] text-muted-foreground">Applying</span>
                    ) : null}
                  </button>
                </div>
                {expanded ? (
                  <div className="ml-6 space-y-1 border-l border-border/60 pl-2">
                    <div className="px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      Slides
                    </div>
                    {template.slides.length === 0 ? (
                      <p className="px-2 py-0.5 text-[10px] text-muted-foreground">No slides in seed</p>
                    ) : (
                      template.slides.map((slide) => (
                        <div
                          key={`${template.id}-${slide.index}`}
                          className="flex items-center gap-2 px-2 py-0.5 text-[11px] text-muted-foreground"
                        >
                          <Presentation size={10} className="flex-shrink-0" />
                          <span className="truncate">{templateSlideLabel(slide)}</span>
                        </div>
                      ))
                    )}
                    <div className="px-2 pt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      Assets
                    </div>
                    {template.assets.length === 0 ? (
                      <p className="px-2 py-0.5 text-[10px] text-muted-foreground">
                        None (images stay inside deck.html)
                      </p>
                    ) : (
                      template.assets.map((asset) => (
                        <div
                          key={`${template.id}-${asset.name}`}
                          className="flex items-center gap-2 px-2 py-0.5 text-[11px] text-muted-foreground"
                        >
                          <ImageIcon size={10} className="flex-shrink-0" />
                          <span className="truncate">{templateAssetLabel(asset)}</span>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      {projects.filter((p) => p.slug !== openSlug).length > 0 ? (
        <div className="mt-2 space-y-0.5 px-1">
          <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Other projects
          </div>
          {projects
            .filter((p) => p.slug !== openSlug)
            .map((p) => (
              <button
                key={p.slug}
                onClick={() => {
                  setSelectedSlug(p.slug);
                  router.push(`${slidesBase}/${p.slug}`);
                }}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-workspace-accent-10"
              >
                <Presentation size={11} className="flex-shrink-0 text-muted-foreground" />
                <span className="truncate">{p.title}</span>
              </button>
            ))}
        </div>
      ) : null}
    </CollapsibleSection>
  );
}
