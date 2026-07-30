'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { Presentation, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
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
  const slidesBase = getWorkspacePath(workspaceId, '/slides');
  const [projects, setProjects] = useState<SlidesProject[]>([]);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

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

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects, pathname]);

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
          title="New Slides Project"
          aria-label="New Slides Project"
          className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent"
        >
          <Plus size={13} />
        </button>
      </div>

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
    </CollapsibleSection>
  );
}
