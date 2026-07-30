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

function friendlyRuntimeDetail(detail: string | null | undefined): string | null {
  if (!detail) return null;
  const trimmed = detail.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('{') || trimmed.includes('"validations"')) {
    return 'Reconnecting to existing runtime…';
  }
  if (trimmed.toLowerCase().includes('already exists')) {
    return 'Reconnecting to existing runtime…';
  }
  return trimmed;
}

async function ensureSlidesRuntime(
  workspaceId: string,
  slug: string,
  attempts = 3,
): Promise<{ ensured: boolean; sidecar_ready?: boolean; detail?: string | null; phase?: string | null }> {
  let lastDetail: string | null = null;
  for (let i = 0; i < attempts; i++) {
    const res = await authFetch(
      `/api/slides/projects/${encodeURIComponent(slug)}/runtime?workspace_id=${encodeURIComponent(workspaceId)}`,
      { method: 'POST' },
    );
    const body = (await res.json().catch(() => ({}))) as {
      ensured?: boolean;
      sidecar_ready?: boolean;
      detail?: string;
      phase?: string;
    };
    if (res.ok && body.ensured) {
      return {
        ensured: true,
        sidecar_ready: Boolean(body.sidecar_ready),
        detail: friendlyRuntimeDetail(body.detail) ?? null,
        phase: body.phase ?? null,
      };
    }
    lastDetail =
      friendlyRuntimeDetail(body.detail) || `Runtime ensure failed (${res.status})`;
    if (i < attempts - 1) {
      await new Promise((r) => setTimeout(r, 1200 * (i + 1)));
    }
  }
  return { ensured: false, detail: lastDetail };
}

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
  const setSelectedTitle = useSlidesStore((s) => s.setSelectedTitle);
  const setEditorMode = useSlidesStore((s) => s.setEditorMode);
  const setRuntimeStatus = useSlidesStore((s) => s.setRuntimeStatus);
  const runtimeStatus = useSlidesStore((s) => s.runtimeStatus);
  const runtimeDetail = useSlidesStore((s) => s.runtimeDetail);

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
    setRuntimeStatus('ensuring');
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
      setSelectedTitle(proj.title);
      // Required Coder runtime for Abi sidecar tools (hard-retry).
      const runtime = await ensureSlidesRuntime(workspaceId, slug, 3);
      if (runtime.ensured && runtime.sidecar_ready) {
        setRuntimeStatus('ready', runtime.phase ? `Runtime ${runtime.phase}` : null);
      } else if (runtime.ensured) {
        setRuntimeStatus(
          'degraded',
          runtime.detail || 'Runtime up but sidecar not ready; Abi falls back to Forgejo',
        );
      } else {
        setRuntimeStatus(
          'error',
          runtime.detail || 'Coder runtime unavailable; Abi can still edit via Forgejo',
        );
      }
    } catch (e) {
      setError((e as Error).message);
      setRuntimeStatus('error', (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, slug, setSelectedSlug, setSelectedTitle, setRuntimeStatus]);

  useEffect(() => {
    setEditorMode(mode);
  }, [mode, setEditorMode]);

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
      setStatus(body.commit_sha ? `Saved ${body.commit_sha.slice(0, 7)}` : 'Saved');
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

      {runtimeStatus === 'ensuring' && (
        <div className="border-b border-border/60 bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          Reconnecting to existing runtime…
        </div>
      )}

      {(runtimeStatus === 'error' || runtimeStatus === 'degraded') && (
        <div
          className={cn(
            'border-b px-4 py-2 text-xs',
            runtimeStatus === 'error'
              ? 'border-amber-500/20 bg-amber-500/10 text-amber-800 dark:text-amber-200'
              : 'border-border/60 bg-muted/40 text-muted-foreground',
          )}
        >
          {runtimeStatus === 'error'
            ? `Coder runtime unavailable: ${runtimeDetail || 'Abi will edit via Forgejo until Coder is back.'}`
            : `Slides runtime degraded: ${runtimeDetail || 'Sidecar not ready; Abi falls back to Forgejo.'}`}
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
