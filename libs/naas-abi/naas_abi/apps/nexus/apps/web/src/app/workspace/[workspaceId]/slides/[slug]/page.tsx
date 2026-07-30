'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SlidesMenuBar, type SlidesEditorMode } from '@/components/slides/slides-menu-bar';
import { authFetch } from '@/stores/auth';
import { useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';
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
  const router = useRouter();
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
  const [mode, setMode] = useState<SlidesEditorMode>('preview');
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');

  const newPresentationHref = `/workspace/${workspaceId}/slides/new`;

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
    // Preview iframe stays mounted (hidden in Code mode) so export stays available.
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

  const menuBar = (
    <SlidesMenuBar
      onNewPresentation={() => router.push(newPresentationHref)}
      onCommit={() => void save()}
      commitDisabled={saving || !dirty || loading}
      onExportPptx={() => void exportPptx()}
      exportDisabled={exporting || loading}
      mode={mode}
      onModeChange={setMode}
      trailing={
        status || dirty || saving ? (
          <div className="ml-2 flex items-center gap-2 border-l border-border pl-2">
            {status && <span className="text-xs text-muted-foreground">{status}</span>}
            {dirty && <span className="text-xs text-amber-600">Unsaved</span>}
            {saving && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
          </div>
        ) : null
      }
    />
  );

  if (loading) {
    return (
      <div className="flex h-full flex-col">
        <Header
          title={title || 'Slides'}
          subtitle={slug ? `slides/${slug}/deck.html` : undefined}
          nav={menuBar}
        />
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading deck…
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header
        title={title}
        subtitle={`slides/${slug}/deck.html · PPTX export is best-effort vs preview`}
        nav={menuBar}
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="relative min-h-0 flex-1">
        {/* Keep iframe mounted so PPTX export and live preview stay warm. */}
        <div
          className={cn(
            'absolute inset-0 flex items-center justify-center bg-muted/20',
            mode !== 'preview' && 'invisible pointer-events-none',
          )}
          aria-hidden={mode !== 'preview'}
        >
          <iframe
            ref={iframeRef}
            title="Slides preview"
            sandbox="allow-scripts allow-same-origin allow-downloads"
            srcDoc={previewHtml}
            className="h-full w-full max-w-6xl bg-white shadow-sm"
          />
        </div>

        {mode === 'code' && (
          <div className="absolute inset-0 min-h-0">
            <MonacoEditor
              height="100%"
              language="html"
              theme="vs-dark"
              value={html}
              onChange={(value) => {
                setHtml(value ?? '');
                setDirty(true);
              }}
              onMount={(editor, monaco) => {
                // Monaco defaults ⌘K to a chord starter; route it to the Abi pane.
                editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, () => {
                  useWorkspaceStore.getState().toggleContextPanel();
                });
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                wordWrap: 'on',
                automaticLayout: true,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
