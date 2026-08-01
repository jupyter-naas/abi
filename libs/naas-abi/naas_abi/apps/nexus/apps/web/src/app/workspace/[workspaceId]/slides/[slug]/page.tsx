'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { SlidesMenuBar, type SlidesEditorMode } from '@/components/slides/slides-menu-bar';
import {
  SlidesPreviewFrame,
  type SlidesPreviewFrameHandle,
} from '@/components/slides/slides-preview-frame';
import { SlidesStatusBar } from '@/components/slides/slides-status-bar';
import { authFetch } from '@/stores/auth';
import {
  SLIDES_DECK_UPDATED_EVENT,
  useSlidesStore,
  type SlidesDeckUpdatedDetail,
} from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';
import { cn } from '@/lib/utils';

function isGitWriteRaceDetail(detail: string): boolean {
  const lowered = detail.toLowerCase();
  return (
    lowered.includes('pushrejected') ||
    lowered.includes('cannot lock ref') ||
    lowered.includes('but expected') ||
    lowered.includes('git write raced') ||
    lowered.includes('deck sync raced') ||
    lowered.includes('deck branch sync raced')
  );
}

function friendlyRuntimeDetail(detail: string | null | undefined): string | null {
  if (!detail) return null;
  const trimmed = detail.trim();
  if (!trimmed) return null;
  if (isGitWriteRaceDetail(trimmed)) {
    return 'Deck branch sync raced; retry open or save. Abi can still edit via Forgejo.';
  }
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
  attempts = 6,
): Promise<{
  ensured: boolean;
  sidecar_ready?: boolean;
  detail?: string | null;
  phase?: string | null;
  coder_workspace?: string | null;
  branch?: string | null;
  coder_ui_url?: string | null;
  environment_id?: string | null;
}> {
  let lastDetail: string | null = null;
  let lastEnsured: {
    ensured: boolean;
    sidecar_ready?: boolean;
    detail?: string | null;
    phase?: string | null;
    coder_workspace?: string | null;
    branch?: string | null;
    coder_ui_url?: string | null;
    environment_id?: string | null;
  } | null = null;
  let lastMeta: {
    coder_workspace?: string | null;
    branch?: string | null;
    coder_ui_url?: string | null;
    environment_id?: string | null;
  } = {};
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
      coder_workspace?: string;
      branch?: string;
      coder_ui_url?: string;
      environment_id?: string;
    };
    lastMeta = {
      coder_workspace: body.coder_workspace ?? lastMeta.coder_workspace,
      branch: body.branch ?? lastMeta.branch,
      coder_ui_url: body.coder_ui_url ?? lastMeta.coder_ui_url,
      environment_id: body.environment_id ?? lastMeta.environment_id,
    };
    if (res.ok && body.ensured) {
      const result = {
        ensured: true,
        sidecar_ready: Boolean(body.sidecar_ready),
        detail: friendlyRuntimeDetail(body.detail) ?? null,
        phase: body.phase ?? null,
        coder_workspace: body.coder_workspace ?? lastMeta.coder_workspace,
        branch: body.branch ?? lastMeta.branch,
        coder_ui_url: body.coder_ui_url ?? lastMeta.coder_ui_url,
        environment_id: body.environment_id ?? lastMeta.environment_id,
      };
      // Settle only when sidecar is healthy. Returning on the first
      // ensured=true stuck the degraded banner while :8378 was still starting.
      if (result.sidecar_ready) {
        return result;
      }
      lastEnsured = result;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, 1500 * Math.min(i + 1, 4)));
        continue;
      }
      return result;
    }
    lastDetail =
      friendlyRuntimeDetail(body.detail) || `Runtime ensure failed (${res.status})`;
    if (i < attempts - 1) {
      await new Promise((r) => setTimeout(r, 1200 * (i + 1)));
    }
  }
  if (lastEnsured) {
    return lastEnsured;
  }
  return {
    ensured: false,
    detail: lastDetail,
    coder_workspace: lastMeta.coder_workspace ?? null,
    branch: lastMeta.branch ?? null,
    coder_ui_url: lastMeta.coder_ui_url ?? null,
    environment_id: lastMeta.environment_id ?? null,
  };
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
  const setRuntimeMeta = useSlidesStore((s) => s.setRuntimeMeta);
  const setDeckDirty = useSlidesStore((s) => s.setDeckDirty);
  const setDeckSource = useSlidesStore((s) => s.setDeckSource);
  const runtimeStatus = useSlidesStore((s) => s.runtimeStatus);
  const runtimeDetail = useSlidesStore((s) => s.runtimeDetail);
  const refreshToken = useSlidesStore((s) => s.refreshToken);

  const [title, setTitle] = useState(slug);
  const [html, setHtml] = useState('');
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [mode, setMode] = useState<SlidesEditorMode>('preview');
  const previewRef = useRef<SlidesPreviewFrameHandle>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const dirtyRef = useRef(false);
  const loadGenRef = useRef(0);
  const skipTokenEffectRef = useRef(true);
  const saveRef = useRef<() => Promise<void>>(async () => {});
  const refreshRef = useRef<() => Promise<void>>(async () => {});

  const newPresentationHref = `/workspace/${workspaceId}/slides/new`;

  useEffect(() => {
    dirtyRef.current = dirty;
    setDeckDirty(dirty);
  }, [dirty, setDeckDirty]);

  useEffect(() => {
    return () => {
      useSlidesStore.getState().setDeckDirty(false);
      useSlidesStore.getState().setDeckSource(null);
    };
  }, []);

  const applyRuntime = useCallback(
    (runtime: Awaited<ReturnType<typeof ensureSlidesRuntime>>) => {
      setRuntimeMeta({
        forgejoBranch: runtime.branch ?? (slug ? `slides/${slug}` : null),
        coderWorkspace: runtime.coder_workspace ?? (slug ? `slides-${slug}` : null),
        coderPhase: runtime.phase ?? null,
        coderUiUrl: runtime.coder_ui_url ?? null,
      });
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
    },
    [setRuntimeMeta, setRuntimeStatus, slug],
  );

  const loadDeck = useCallback(
    async (opts?: { quiet?: boolean; ensureRuntime?: boolean }) => {
      if (!workspaceId || !slug) return;
      const quiet = Boolean(opts?.quiet);
      const ensureRuntime = opts?.ensureRuntime !== false;
      const gen = ++loadGenRef.current;
      if (quiet) {
        setRefreshing(true);
      } else {
        setLoading(true);
        setRuntimeStatus('ensuring');
      }
      setError(null);
      try {
        const [projRes, deckRes] = await Promise.all([
          authFetch(
            `/api/slides/projects/${encodeURIComponent(slug)}?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
          authFetch(
            `/api/slides/projects/${encodeURIComponent(slug)}/deck?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
        ]);
        if (gen !== loadGenRef.current) return;
        if (!projRes.ok || !deckRes.ok) {
          const body = (await (projRes.ok ? deckRes : projRes)
            .json()
            .catch(() => ({}))) as { detail?: string };
          throw new Error(body.detail || 'Failed to load deck');
        }
        const proj = (await projRes.json()) as {
          title: string;
          branch?: string;
        };
        const deck = (await deckRes.json()) as { html: string; source?: string };
        if (gen !== loadGenRef.current) return;
        setTitle(proj.title);
        setHtml(deck.html);
        setPreviewHtml(deck.html);
        setDirty(false);
        setDeckSource(
          deck.source === 'sidecar' || deck.source === 'forgejo' ? deck.source : null,
        );
        setSelectedSlug(slug);
        setSelectedTitle(proj.title);
        setRuntimeMeta({
          forgejoBranch: proj.branch || `slides/${slug}`,
          coderWorkspace: `slides-${slug}`,
        });
        if (quiet) {
          const src =
            deck.source === 'sidecar'
              ? 'workspace'
              : deck.source === 'forgejo'
                ? 'Forgejo snapshot'
                : null;
          setStatus(src ? `Preview refreshed (${src})` : 'Preview refreshed');
        }
        if (ensureRuntime) {
          const runtime = await ensureSlidesRuntime(workspaceId, slug, quiet ? 2 : 6);
          if (gen !== loadGenRef.current) return;
          applyRuntime(runtime);
        }
      } catch (e) {
        if (gen !== loadGenRef.current) return;
        const message = (e as Error).message;
        // Deck load Forgejo races are not a Coder outage; keep banners separate.
        setError(
          isGitWriteRaceDetail(message)
            ? 'Deck sync raced on Forgejo; refresh to retry.'
            : message,
        );
        if (!quiet && !isGitWriteRaceDetail(message)) {
          setRuntimeStatus('error', message);
        } else if (!quiet) {
          setRuntimeStatus('degraded', friendlyRuntimeDetail(message));
        }
      } finally {
        if (gen === loadGenRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [
      workspaceId,
      slug,
      setSelectedSlug,
      setSelectedTitle,
      setRuntimeStatus,
      setRuntimeMeta,
      setDeckSource,
      applyRuntime,
    ],
  );

  const refresh = useCallback(async () => {
    if (dirtyRef.current) {
      const ok = window.confirm(
        'You have unsaved local edits. Refresh from the live workspace (Coder when ready; Forgejo snapshot otherwise) and discard them?',
      );
      if (!ok) return;
    }
    await loadDeck({ quiet: true, ensureRuntime: true });
  }, [loadDeck]);

  useEffect(() => {
    void loadDeck({ quiet: false, ensureRuntime: true });
  }, [loadDeck]);

  // Auto-refresh when Abi (or store) bumps refreshToken after a slides write tool.
  useEffect(() => {
    if (skipTokenEffectRef.current) {
      skipTokenEffectRef.current = false;
      return;
    }
    if (!refreshToken) return;
    if (dirtyRef.current) {
      setStatus('Deck updated on server (unsaved local edits kept; use View → Refresh)');
      return;
    }
    void loadDeck({ quiet: true, ensureRuntime: false });
  }, [refreshToken, loadDeck]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<SlidesDeckUpdatedDetail>).detail;
      if (detail?.slug && detail.slug !== slug) return;
      useSlidesStore.getState().requestDeckRefresh(detail?.slug ?? slug);
    };
    window.addEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SLIDES_DECK_UPDATED_EVENT, onUpdated);
  }, [slug]);

  useEffect(() => {
    setEditorMode(mode);
  }, [mode, setEditorMode]);

  useEffect(() => {
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => setPreviewHtml(html), 350);
    return () => {
      if (previewTimer.current) clearTimeout(previewTimer.current);
    };
  }, [html]);

  const save = useCallback(async () => {
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
  }, [workspaceId, slug, html]);

  useEffect(() => {
    saveRef.current = save;
  }, [save]);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  // ⌘/Ctrl+S Save, ⌘/Ctrl+R Refresh (intercept browser reload).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      if (!mod) return;
      const key = event.key.toLowerCase();
      if (key === 's') {
        event.preventDefault();
        event.stopPropagation();
        void saveRef.current();
        return;
      }
      if (key === 'r') {
        event.preventDefault();
        event.stopPropagation();
        void refreshRef.current();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  const exportPptx = async () => {
    // Preview iframe stays mounted (hidden in Code mode) so export stays available.
    // Export goes through postMessage; sandbox omits allow-same-origin.
    if (!previewRef.current) {
      setError('Preview is not ready for PPTX export.');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      await previewRef.current.exportPptx();
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
      onRefresh={() => void refresh()}
      refreshDisabled={loading || refreshing}
      trailing={
        status || dirty || saving || refreshing ? (
          <div className="ml-2 flex items-center gap-2 border-l border-border pl-2">
            {status && <span className="text-xs text-muted-foreground">{status}</span>}
            {dirty && <span className="text-xs text-amber-600">Unsaved</span>}
            {(saving || refreshing) && (
              <Loader2 size={14} className="animate-spin text-muted-foreground" />
            )}
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
        <SlidesStatusBar />
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
            ? runtimeDetail && isGitWriteRaceDetail(runtimeDetail)
              ? runtimeDetail
              : `Coder runtime unavailable: ${runtimeDetail || 'Abi will edit via Forgejo until Coder is back.'}`
            : `Slides runtime degraded: ${runtimeDetail || 'Sidecar not ready; Abi falls back to Forgejo.'}`}
        </div>
      )}

      <div className="relative min-h-0 flex-1">
        {/* Keep iframe mounted so PPTX export and live preview stay warm. */}
        <div
          className={cn(
            'absolute inset-0',
            mode !== 'preview' && 'invisible pointer-events-none',
          )}
          aria-hidden={mode !== 'preview'}
        >
          <SlidesPreviewFrame ref={previewRef} html={previewHtml} />
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
                // Override Monaco save / browser-reload chords for Slides.
                editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
                  void saveRef.current();
                });
                editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyR, () => {
                  void refreshRef.current();
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

      <SlidesStatusBar onRefresh={() => void refresh()} refreshing={refreshing} />
    </div>
  );
}
