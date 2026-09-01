'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, Presentation } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SlidesMenuBar } from '@/components/slides/slides-menu-bar';
import { SlidesStatusBar } from '@/components/slides/slides-status-bar';
import { slidesApiErrorMessage, startNewPresentation } from '@/lib/create-slides-project';
import { authFetch } from '@/stores/auth';
import { useSlidesStore, type SlidesProject } from '@/stores/slides';

export default function SlidesIndexPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/slides`;
  const [projects, setProjects] = useState<SlidesProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

  const onNewPresentation = useCallback(async () => {
    if (!workspaceId || creating) return;
    setCreating(true);
    setError(null);
    try {
      await startNewPresentation(workspaceId, (href) => router.push(href));
    } catch (e) {
      setError(slidesApiErrorMessage((e as Error).message, 'Could not create the deck.'));
      setCreating(false);
    }
  }, [workspaceId, creating, router]);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(
        `/api/slides/projects?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        throw new Error(slidesApiErrorMessage(body.detail, `Failed (${res.status})`));
      }
      setProjects((await res.json()) as SlidesProject[]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex h-full flex-col">
      <Header
        title="Slides"
        nav={<SlidesMenuBar onNewPresentation={() => void onNewPresentation()} />}
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" />
            Loading projects…
          </div>
        ) : projects.length === 0 ? (
          <div className="mx-auto max-w-lg space-y-3 pt-16 text-center">
            <Presentation size={32} className="mx-auto text-muted-foreground" />
            <h2 className="text-base font-medium">Create your first deck</h2>
            <p className="text-sm text-muted-foreground">
              Use File → New or New in the Slides column. That opens Minimal Light and
              Slides. Talk through the deck; the preview updates as tools run. File →
              Export PPTX rebuilds the current HTML at 1280x720 (closest fit, not
              pixel-perfect).
            </p>
          </div>
        ) : (
          <div className="mx-auto grid max-w-3xl gap-2">
            {projects.map((p) => (
              <button
                key={p.slug}
                type="button"
                onClick={() => {
                  setSelectedSlug(p.slug);
                  router.push(`${base}/${p.slug}`);
                }}
                className="flex w-full items-center justify-between rounded-md border border-border px-4 py-3 text-left transition-colors hover:bg-workspace-accent-5"
              >
                <div>
                  <div className="text-sm font-medium">{p.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.branch} · {p.deck_path}
                  </div>
                </div>
                <span className="text-xs text-muted-foreground">{p.slug}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <SlidesStatusBar />
    </div>
  );
}
