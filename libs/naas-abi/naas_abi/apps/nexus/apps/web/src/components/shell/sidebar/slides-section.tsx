'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import {
  ChevronRight,
  FileCode2,
  Folder,
  Image as ImageIcon,
  Plus,
  Presentation,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { useSlidesStore, type SlidesProject } from '@/stores/slides';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface TreeEntry {
  name: string;
  path: string;
  type: 'file' | 'dir';
  size?: number;
}

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
  const [tree, setTree] = useState<TreeEntry[]>([]);
  const [assets, setAssets] = useState<TreeEntry[]>([]);
  const [assetsOpen, setAssetsOpen] = useState(true);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

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

  const fetchTree = useCallback(async () => {
    if (!workspaceId || !openSlug) {
      setTree([]);
      setAssets([]);
      return;
    }
    try {
      const res = await authFetch(
        `/api/slides/projects/${encodeURIComponent(openSlug)}/tree?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) {
        // Fallback shape when tree API unavailable (older pin).
        setTree([
          { name: 'deck.html', path: `slides/${openSlug}/deck.html`, type: 'file' },
          { name: 'assets', path: `slides/${openSlug}/assets`, type: 'dir' },
        ]);
        setAssets([]);
        return;
      }
      const body = (await res.json()) as {
        entries?: TreeEntry[];
        assets?: TreeEntry[];
      };
      setTree(body.entries ?? []);
      setAssets(body.assets ?? []);
    } catch {
      setTree([
        { name: 'deck.html', path: `slides/${openSlug}/deck.html`, type: 'file' },
        { name: 'assets', path: `slides/${openSlug}/assets`, type: 'dir' },
      ]);
      setAssets([]);
    }
  }, [workspaceId, openSlug]);

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects, pathname]);

  useEffect(() => {
    void fetchTree();
  }, [fetchTree]);

  useEffect(() => {
    if (routeSlug) setSelectedSlug(routeSlug);
  }, [routeSlug, setSelectedSlug]);

  const folderLabel = openProject?.title || openSlug || 'Presentation';

  return (
    <CollapsibleSection
      id="slides"
      icon={<Presentation size={18} />}
      label="Slides"
      description="Presentation projects"
      href={slidesBase}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="flex items-center justify-between px-1 pb-1">
        <button
          onClick={() => router.push(slidesBase)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium hover:bg-workspace-accent-10',
            pathname === slidesBase && 'text-workspace-accent',
          )}
        >
          All projects
        </button>
        <button
          onClick={() => router.push(`${slidesBase}/new`)}
          title="New Presentation"
          aria-label="New Presentation"
          className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent"
        >
          <Plus size={13} />
        </button>
      </div>

      {openSlug ? (
        <div className="space-y-0.5 px-1">
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

          <div className="ml-3 space-y-0.5 border-l border-border/60 pl-2">
            {(tree.length
              ? tree.filter((e) => e.type === 'file' && e.name !== 'project.json')
              : [{ name: 'deck.html', path: '', type: 'file' as const }]
            ).map((entry) => (
              <button
                key={entry.name}
                type="button"
                onClick={() => router.push(`${slidesBase}/${openSlug}`)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-workspace-accent-10',
                  entry.name === 'deck.html' &&
                    pathname.startsWith(`${slidesBase}/${openSlug}`) &&
                    'bg-workspace-accent-10 font-medium text-workspace-accent',
                )}
              >
                <FileCode2 size={11} className="flex-shrink-0 text-muted-foreground" />
                <span className="truncate">{entry.name}</span>
              </button>
            ))}

            <button
              type="button"
              onClick={() => setAssetsOpen((v) => !v)}
              className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-xs text-foreground hover:bg-workspace-accent-10"
            >
              <ChevronRight
                size={11}
                className={cn('transition-transform', assetsOpen && 'rotate-90')}
              />
              <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
              <span className="truncate">assets</span>
            </button>
            {assetsOpen && (
              <div className="ml-4 space-y-0.5">
                {assets.length === 0 ? (
                  <p className="px-2 py-0.5 text-[10px] text-muted-foreground">
                    Empty (template images still embedded in deck.html)
                  </p>
                ) : (
                  assets.map((entry) => (
                    <div
                      key={entry.path}
                      className="flex items-center gap-2 px-2 py-0.5 text-[11px] text-muted-foreground"
                    >
                      <ImageIcon size={10} className="flex-shrink-0" />
                      <span className="truncate">{entry.name}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {projects.length > 1 && (
            <>
              <div className="mt-2 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
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
            </>
          )}
        </div>
      ) : (
        <div className="space-y-0.5 px-1">
          <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Projects
          </div>
          {projects.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">No slides projects yet</p>
          ) : (
            projects.map((p) => {
              const href = `${slidesBase}/${p.slug}`;
              const active = pathname.startsWith(href);
              return (
                <button
                  key={p.slug}
                  onClick={() => {
                    setSelectedSlug(p.slug);
                    router.push(href);
                  }}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-workspace-accent-10',
                    active
                      ? 'bg-workspace-accent-10 font-medium text-workspace-accent'
                      : 'text-foreground',
                  )}
                >
                  <Presentation size={11} className="flex-shrink-0 text-muted-foreground" />
                  <span className="truncate">{p.title}</span>
                </button>
              );
            })
          )}
        </div>
      )}
    </CollapsibleSection>
  );
}
