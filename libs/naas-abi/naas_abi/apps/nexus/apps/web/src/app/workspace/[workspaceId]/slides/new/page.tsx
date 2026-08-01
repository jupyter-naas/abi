'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Check, Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SlidesMenuBar } from '@/components/slides/slides-menu-bar';
import { SlidesStatusBar } from '@/components/slides/slides-status-bar';
import { authFetch } from '@/stores/auth';
import { useSlidesStore } from '@/stores/slides';

type SeedTemplate = {
  id: string;
  name: string;
  description: string;
  preview_bg: string;
  preview_panel: string;
  preview_accent: string;
  preview_ink: string;
};

function TemplateThumb({ t }: { t: SeedTemplate }) {
  return (
    <div
      className="relative aspect-video w-full overflow-hidden rounded-sm border border-black/10"
      style={{ background: t.preview_bg }}
      aria-hidden
    >
      <div
        className="absolute inset-[10%] flex flex-col rounded-[2px] shadow-sm"
        style={{ background: t.preview_panel, border: `1px solid ${t.preview_accent}33` }}
      >
        <div className="h-[28%]" style={{ background: t.preview_accent }} />
        <div className="flex flex-1 flex-col justify-center gap-1.5 px-[8%]">
          <div className="h-1.5 w-[18%] rounded-full" style={{ background: t.preview_accent }} />
          <div className="h-2 w-[72%] rounded-full" style={{ background: t.preview_ink, opacity: 0.85 }} />
          <div className="h-1.5 w-[48%] rounded-full" style={{ background: t.preview_ink, opacity: 0.35 }} />
        </div>
      </div>
    </div>
  );
}

export default function NewSlidesProjectPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/slides`;
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

  const [templates, setTemplates] = useState<SeedTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateId, setTemplateId] = useState('minimal-light-v1');
  const [title, setTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slugValid = !slug || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    setTemplatesLoading(true);
    void (async () => {
      try {
        const res = await authFetch(
          `/api/slides/templates?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(body?.detail || `Templates failed (${res.status})`);
        }
        const rows = (await res.json()) as SeedTemplate[];
        if (cancelled) return;
        setTemplates(rows);
        setTemplateId((current) =>
          rows.some((r) => r.id === current) ? current : rows[0]?.id || 'minimal-light-v1',
        );
      } catch (e) {
        if (cancelled) return;
        setError((e as Error).message);
        setTemplates([
          {
            id: 'minimal-light-v1',
            name: 'Minimal Light',
            description: 'Quiet light deck with generous whitespace and a single accent.',
            preview_bg: '#f7f6f3',
            preview_panel: '#ffffff',
            preview_accent: '#1a1a1a',
            preview_ink: '#1a1a1a',
          },
        ]);
      } finally {
        if (!cancelled) setTemplatesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const create = async () => {
    if (!title.trim() || !slugValid || !templateId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch('/api/slides/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          title: title.trim(),
          slug: slug.trim() || undefined,
          template_id: templateId,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body?.detail || `Failed (${res.status})`);
      }
      const created = (await res.json()) as { slug: string };
      setSelectedSlug(created.slug);
      router.push(`${base}/${created.slug}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <Header
        title="New Presentation"
        nav={<SlidesMenuBar onNewPresentation={() => router.push(`${base}/new`)} />}
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-4xl space-y-8">
          <section className="space-y-3">
            <div className="flex items-baseline justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">Templates</h2>
                <p className="text-xs text-muted-foreground">
                  Show all templates. Pick a seed, then name the deck. Abi customizes after create.
                </p>
              </div>
              <span className="text-xs text-muted-foreground">
                {templatesLoading ? 'Loading…' : `${templates.length} templates`}
              </span>
            </div>

            {templatesLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                Loading templates…
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {templates.map((t) => {
                  const selected = t.id === templateId;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTemplateId(t.id)}
                      className={`group relative rounded-md border p-2.5 text-left transition ${
                        selected
                          ? 'border-workspace-accent bg-workspace-accent-10 ring-1 ring-workspace-accent'
                          : 'border-border hover:border-workspace-accent/50'
                      }`}
                    >
                      <TemplateThumb t={t} />
                      <div className="mt-2.5 space-y-0.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium">{t.name}</span>
                          {selected && (
                            <Check size={14} className="shrink-0 text-workspace-accent" />
                          )}
                        </div>
                        <p className="line-clamp-2 text-xs text-muted-foreground">
                          {t.description}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          <section className="mx-auto max-w-xl space-y-5">
            <label className="block space-y-1">
              <span className="text-sm font-medium">Title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Q3 Business Review"
                autoFocus
                className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-workspace-accent"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-sm font-medium">Slug (optional)</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase())}
                placeholder="q3-business-review"
                className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-workspace-accent"
              />
              <span className="text-xs text-muted-foreground">
                Stored on branch slides/&lt;slug&gt; as slides/&lt;slug&gt;/deck.html
              </span>
              {slug && !slugValid && (
                <span className="block text-xs text-red-600">Use lowercase kebab-case</span>
              )}
            </label>

            <div className="rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
              Template: {templates.find((t) => t.id === templateId)?.name || templateId} (
              {templateId}). A hidden slides runtime may start in the background; you will never
              see the Coder UI.
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void create()}
                disabled={busy || !title.trim() || !slugValid || !templateId}
                className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy && <Loader2 size={14} className="animate-spin" />}
                Create project
              </button>
              <button
                type="button"
                onClick={() => router.push(base)}
                className="rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:bg-workspace-accent-10"
              >
                Cancel
              </button>
            </div>
          </section>
        </div>
      </div>
      <SlidesStatusBar />
    </div>
  );
}
