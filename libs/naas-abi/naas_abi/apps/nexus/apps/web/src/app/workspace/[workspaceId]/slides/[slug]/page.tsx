'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams } from 'next/navigation';
import { Download, Loader2, Presentation, Save } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useSlidesStore } from '@/stores/slides';
import { cn } from '@/lib/utils';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      Loading editor…
    </div>
  ),
});

export default function SlidesEditorPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const slug = typeof params?.slug === 'string' ? params.slug : '';
  const setSelectedSlug = useSlidesStore((s) => s.setSelectedSlug);

  const [title, setTitle] = useState(slug);
  const [html, setHtml] = useState('');
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [split, setSplit] = useState(0.55);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');

  const load = useCallback(async () => {
    if (!workspaceId || !slug) return;
    setLoading(true);
    setError(null);
    try {
      const [projRes, deckRes] = await Promise.all([
        authFetch(
          `/api/slides/projects/${encodeURIComponent(slug)}?workspace_id=${encodeURIComponent(workspaceId)}`,
        ),
        authFetch(
          `/api/slides/projects/${encodeURIComponent(slug)}/deck?workspace_id=${encodeURIComponent(workspaceId)}`,
        ),
      ]);
      if (!projRes.ok || !deckRes.ok) {
        const body = (await (projRes.ok ? deckRes : projRes)
          .json()
          .catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail || 'Failed to load deck');
      }
      const proj = (await projRes.json()) as { title: string };
      const deck = (await deckRes.json()) as { html: string };
      setTitle(proj.title);
      setHtml(deck.html);
      setPreviewHtml(deck.html);
      setDirty(false);
      setSelectedSlug(slug);
      // Invisible runtime ensure (best-effort).
      void authFetch(
        `/api/slides/projects/${encodeURIComponent(slug)}/runtime?workspace_id=${encodeURIComponent(workspaceId)}`,
        { method: 'POST' },
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, slug, setSelectedSlug]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => setPreviewHtml(html), 350);
    return () => {
      if (previewTimer.current) clearTimeout(previewTimer.current);
    };
  }, [html]);

  const save = async () => {
    if (!workspaceId || !slug || !html) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const res = await authFetch(`/api/slides/projects/${encodeURIComponent(slug)}/deck`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          html,
          message: `Update deck ${slug}`,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail || `Save failed (${res.status})`);
      }
      const body = (await res.json()) as { commit_sha?: string };
      setDirty(false);
      setStatus(body.commit_sha ? `Committed ${body.commit_sha.slice(0, 7)}` : 'Saved');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const exportPptx = async () => {
    const win = iframeRef.current?.contentWindow as
      | (Window & { buildPptx?: () => Promise<unknown> | unknown })
      | null;
    if (!win?.buildPptx) {
      setError('Preview is not ready for PPTX export (buildPptx missing).');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      await Promise.resolve(win.buildPptx());
      setStatus('PPTX export started (best-effort vs preview)');
    } catch (e) {
      setError(`PPTX export failed: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={16} className="animate-spin" />
        Loading deck…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center justify-between gap-3 border-b border-border/50 px-4">
        <div className="flex min-w-0 items-center gap-3">
          <Presentation size={18} className="flex-shrink-0 text-workspace-accent" />
          <div className="min-w-0">
            <h1 className="truncate text-sm font-medium">{title}</h1>
            <p className="truncate text-[11px] text-muted-foreground">
              slides/{slug}/deck.html · PPTX export is best-effort vs preview
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {status && <span className="text-xs text-muted-foreground">{status}</span>}
          {dirty && <span className="text-xs text-amber-600">Unsaved</span>}
          <button
            onClick={() => void save()}
            disabled={saving || !dirty}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-workspace-accent-10 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Commit
          </button>
          <button
            onClick={() => void exportPptx()}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Export PPTX
          </button>
        </div>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 border-r border-border/50" style={{ width: `${split * 100}%` }}>
          <div className="flex h-8 items-center border-b border-border/50 px-3 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Preview
          </div>
          <iframe
            ref={iframeRef}
            title="Slides preview"
            sandbox="allow-scripts allow-same-origin allow-downloads"
            srcDoc={previewHtml}
            className="h-[calc(100%-2rem)] w-full bg-white"
          />
        </div>
        <div
          className="w-1 cursor-col-resize bg-border/40 hover:bg-workspace-accent"
          onMouseDown={(e) => {
            e.preventDefault();
            const startX = e.clientX;
            const start = split;
            const onMove = (ev: MouseEvent) => {
              const parent = (e.target as HTMLElement).parentElement;
              if (!parent) return;
              const width = parent.getBoundingClientRect().width;
              const next = Math.min(0.8, Math.max(0.25, start + (ev.clientX - startX) / width));
              setSplit(next);
            };
            const onUp = () => {
              window.removeEventListener('mousemove', onMove);
              window.removeEventListener('mouseup', onUp);
            };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
          }}
        />
        <div className={cn('min-w-0 flex-1')}>
          <div className="flex h-8 items-center border-b border-border/50 px-3 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Code
          </div>
          <div className="h-[calc(100%-2rem)]">
            <MonacoEditor
              height="100%"
              language="html"
              theme="vs-dark"
              value={html}
              onChange={(value) => {
                setHtml(value ?? '');
                setDirty(true);
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                wordWrap: 'on',
                automaticLayout: true,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
