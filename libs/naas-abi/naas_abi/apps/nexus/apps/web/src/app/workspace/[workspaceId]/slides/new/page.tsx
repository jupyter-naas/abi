'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, Presentation } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useSlidesStore } from '@/stores/slides';

export default function NewSlidesProjectPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const base = `/workspace/${workspaceId}/slides`;
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

  const [title, setTitle] = useState('');
  const [slug, setSlug] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slugValid = !slug || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug);

  const create = async () => {
    if (!title.trim() || !slugValid) return;
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
          template_id: 'bob-fmz-v1',
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
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <Presentation size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">New Slides Project</h1>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-xl space-y-5">
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
            Template: BOB / Forvis Mazars (bob-fmz-v1). A hidden slides runtime may start in
            the background; you will never see the Coder UI.
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => void create()}
              disabled={busy || !title.trim() || !slugValid}
              className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              Create project
            </button>
            <button
              onClick={() => router.push(base)}
              className="rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:bg-workspace-accent-10"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
