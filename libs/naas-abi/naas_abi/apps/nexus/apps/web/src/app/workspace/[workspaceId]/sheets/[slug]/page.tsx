'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { MonacoEditor } from '@/components/monaco/monaco-editor';
import { Header } from '@/components/shell/header';
import {
  isSheetsTypingTarget,
  SheetsMenuBar,
  type SheetsEditorMode,
} from '@/components/sheets/sheets-menu-bar';
import { SheetsPreviewFrame } from '@/components/sheets/sheets-preview-frame';
import { downloadSheetsHtml, resolveSheetsPreviewAssets } from '@/components/sheets/sheets-assets';
import {
  applySheetsTextEdits,
  collectSheetsTextEdits,
  sanitizeSheetsEditHtml,
  SHEETS_MANUAL_EDIT_IDLE_MS,
  type SheetsTextEdit,
} from '@/components/sheets/sheets-preview-fit';
import {
  clampTabIndex,
  deleteWorkbookTab,
  duplicateWorkbookTab,
  insertWorkbookTab,
  parseWorkbookTabs,
  reorderWorkbookTabs,
  type TabMutationResult,
} from '@/components/sheets/sheets-outline';
import { downloadSheetsWorkbookXlsx } from '@/lib/export-sheets-workbook-xlsx';
import { SheetsStatusBar } from '@/components/sheets/sheets-status-bar';
import {
  openSheetsAgentPane,
  sheetsApiErrorMessage,
  startNewWorkbook,
} from '@/lib/create-sheets-project';
import { copyWorkbookToMyDrive } from '@/lib/sheets-my-drive';
import { authFetch } from '@/stores/auth';
import {
  SHEETS_DECK_UPDATED_EVENT,
  useSheetsStore,
  type SheetsWorkbookUpdatedDetail,
} from '@/stores/sheets';
import { cn } from '@/lib/utils';

function isGitWriteRaceDetail(detail: string): boolean {
  const lowered = detail.toLowerCase();
  return (
    lowered.includes('pushrejected') ||
    lowered.includes('cannot lock ref') ||
    lowered.includes('but expected') ||
    lowered.includes('git write raced') ||
    lowered.includes('workbook sync raced') ||
    lowered.includes('workbook branch sync raced')
  );
}

function friendlyRuntimeDetail(detail: string | null | undefined): string | null {
  if (!detail) return null;
  const trimmed = detail.trim();
  if (!trimmed) return null;
  if (isGitWriteRaceDetail(trimmed)) {
    return 'Workbook branch sync raced; retry open or save. Abi can still edit via Forgejo.';
  }
  if (trimmed.startsWith('{') || trimmed.includes('"validations"')) {
    return 'Reconnecting to existing runtime…';
  }
  if (trimmed.toLowerCase().includes('already exists')) {
    return 'Reconnecting to existing runtime…';
  }
  return trimmed;
}

async function ensureSheetsRuntime(
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
      `/api/sheets/projects/${encodeURIComponent(slug)}/runtime?workspace_id=${encodeURIComponent(workspaceId)}`,
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

export default function SheetsEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const slug = typeof params?.slug === 'string' ? params.slug : '';
  const setSelectedSlug = useSheetsStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useSheetsStore((s) => s.setSelectedTitle);
  const selectedIndex = useSheetsStore((s) => s.selectedIndex);
  const setSelectedIndex = useSheetsStore((s) => s.setSelectedIndex);
  const setTabCount = useSheetsStore((s) => s.setTabCount);
  const setFilmstrip = useSheetsStore((s) => s.setFilmstrip);
  const setReorderOpenWorkbook = useSheetsStore((s) => s.setReorderOpenWorkbook);
  const setEditorMode = useSheetsStore((s) => s.setEditorMode);
  const setRuntimeStatus = useSheetsStore((s) => s.setRuntimeStatus);
  const setRuntimeMeta = useSheetsStore((s) => s.setRuntimeMeta);
  const setWorkbookDirty = useSheetsStore((s) => s.setWorkbookDirty);
  const setWorkbookSource = useSheetsStore((s) => s.setWorkbookSource);
  const runtimeStatus = useSheetsStore((s) => s.runtimeStatus);
  const runtimeDetail = useSheetsStore((s) => s.runtimeDetail);
  const refreshToken = useSheetsStore((s) => s.refreshToken);
  const agentWriting = useSheetsStore((s) => s.agentWriting);

  const [title, setTitle] = useState(slug);
  const [html, setHtml] = useState('');
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingToDrive, setSavingToDrive] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [mode, setMode] = useState<SheetsEditorMode>('preview');
  const [manualEdit, setManualEdit] = useState(false);
  const [holdPreview, setHoldPreview] = useState(false);
  const [mutating, setMutating] = useState(false);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const dirtyRef = useRef(false);
  const htmlRef = useRef('');
  const manualEditRef = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadGenRef = useRef(0);
  const skipTokenEffectRef = useRef(true);
  const saveRef = useRef<() => Promise<void>>(async () => {});
  const refreshRef = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    if (!slug) return;
    openSheetsAgentPane({ slug });
  }, [slug]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [slug, setSelectedIndex]);

  useEffect(() => {
    dirtyRef.current = dirty;
    setWorkbookDirty(dirty);
  }, [dirty, setWorkbookDirty]);

  useEffect(() => {
    htmlRef.current = html;
  }, [html]);

  useEffect(() => {
    manualEditRef.current = manualEdit;
  }, [manualEdit]);

  useEffect(() => {
    return () => {
      useSheetsStore.getState().setWorkbookDirty(false);
      useSheetsStore.getState().setWorkbookSource(null);
    };
  }, []);

  const applyRuntime = useCallback(
    (runtime: Awaited<ReturnType<typeof ensureSheetsRuntime>>) => {
      setRuntimeMeta({
        forgejoBranch: runtime.branch ?? (slug ? `sheets/${slug}` : null),
        coderWorkspace: runtime.coder_workspace ?? (slug ? `sheets-${slug}` : null),
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

  const loadWorkbook = useCallback(
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
        const [projRes, workbookRes] = await Promise.all([
          authFetch(
            `/api/sheets/projects/${encodeURIComponent(slug)}?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
          authFetch(
            `/api/sheets/projects/${encodeURIComponent(slug)}/workbook?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
        ]);
        if (gen !== loadGenRef.current) return;
        if (!projRes.ok || !workbookRes.ok) {
          const body = (await (projRes.ok ? workbookRes : projRes)
            .json()
            .catch(() => ({}))) as { detail?: unknown };
          throw new Error(sheetsApiErrorMessage(body.detail, 'Failed to load workbook'));
        }
        const proj = (await projRes.json()) as {
          title: string;
          branch?: string;
        };
        const workbook = (await workbookRes.json()) as { html: string; source?: string };
        if (gen !== loadGenRef.current) return;
        setTitle(proj.title);
        setHoldPreview(false);
        setHtml(workbook.html);
        setPreviewHtml(workbook.html);
        setSelectedIndex(
          clampTabIndex(
            useSheetsStore.getState().selectedIndex,
            parseWorkbookTabs(workbook.html).length,
          ),
        );
        setDirty(false);
        setWorkbookSource(
          workbook.source === 'sidecar' || workbook.source === 'forgejo' ? workbook.source : null,
        );
        setSelectedSlug(slug);
        setSelectedTitle(proj.title);
        setRuntimeMeta({
          forgejoBranch: proj.branch || `sheets/${slug}`,
          coderWorkspace: `sheets-${slug}`,
        });
        if (quiet) {
          const src =
            workbook.source === 'sidecar'
              ? 'workspace'
              : workbook.source === 'forgejo'
                ? 'Forgejo snapshot'
                : null;
          setStatus(src ? `Preview refreshed (${src})` : 'Preview refreshed');
        }
        setLoading(false);
        setRefreshing(false);
        if (ensureRuntime) {
          const runtime = await ensureSheetsRuntime(workspaceId, slug, quiet ? 2 : 6);
          if (gen !== loadGenRef.current) return;
          applyRuntime(runtime);
        }
      } catch (e) {
        if (gen !== loadGenRef.current) return;
        const message = (e as Error).message;
        // Workbook load Forgejo races are not a Coder outage; keep banners separate.
        setError(
          isGitWriteRaceDetail(message)
            ? 'Workbook sync raced on Forgejo; refresh to retry.'
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
      setWorkbookSource,
      setSelectedIndex,
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
    await loadWorkbook({ quiet: true, ensureRuntime: true });
  }, [loadWorkbook]);

  useEffect(() => {
    void loadWorkbook({ quiet: false, ensureRuntime: true });
  }, [loadWorkbook]);

  // Auto-refresh when Abi (or store) bumps refreshToken after a sheets write tool.
  useEffect(() => {
    if (skipTokenEffectRef.current) {
      skipTokenEffectRef.current = false;
      return;
    }
    if (!refreshToken) return;
    if (dirtyRef.current) {
      setStatus('Workbook updated on server (unsaved local edits kept; use View → Refresh)');
      return;
    }
    void loadWorkbook({ quiet: true, ensureRuntime: false });
  }, [refreshToken, loadWorkbook]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<SheetsWorkbookUpdatedDetail>).detail;
      if (detail?.slug && detail.slug !== slug) return;
      useSheetsStore.getState().requestWorkbookRefresh(detail?.slug ?? slug);
    };
    window.addEventListener(SHEETS_DECK_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(SHEETS_DECK_UPDATED_EVENT, onUpdated);
  }, [slug]);

  useEffect(() => {
    setEditorMode(mode);
  }, [mode, setEditorMode]);

  useEffect(() => {
    if (holdPreview) return;
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => setPreviewHtml(html), 350);
    return () => {
      if (previewTimer.current) clearTimeout(previewTimer.current);
    };
  }, [html, holdPreview]);

  const save = useCallback(async () => {
    const workbook = htmlRef.current;
    if (!workspaceId || !slug || !workbook) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const res = await authFetch(`/api/sheets/projects/${encodeURIComponent(slug)}/workbook`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          html: workbook,
          message: `chore(workbook): update ${slug}`,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        throw new Error(sheetsApiErrorMessage(body.detail, `Save failed (${res.status})`));
      }
      const body = (await res.json()) as { commit_sha?: string };
      setDirty(false);
      setStatus(body.commit_sha ? `Saved ${body.commit_sha.slice(0, 7)}` : 'Saved');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [workspaceId, slug]);

  const saveToMyDrive = useCallback(async () => {
    if (!slug || !html) return;
    setSavingToDrive(true);
    setError(null);
    setStatus(null);
    try {
      const { relativePath } = await copyWorkbookToMyDrive({
        slug,
        html,
        title,
        workspaceId,
      });
      setStatus(`Copied to My Drive: ${relativePath}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSavingToDrive(false);
    }
  }, [slug, html, title, workspaceId]);

  useEffect(() => {
    saveRef.current = save;
  }, [save]);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  const deleteSelectedTabRef = useRef<() => void>(() => {});

  // ⌘/Ctrl+S Save, ⌘/Ctrl+R Refresh (intercept browser reload). Delete tab when not typing.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      if (!mod) {
        if (
          event.key === 'Delete' &&
          !manualEditRef.current &&
          !isSheetsTypingTarget(event.target)
        ) {
          event.preventDefault();
          deleteSelectedTabRef.current();
        }
        return;
      }
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

  const exportXlsx = async () => {
    if (!workspaceId || !slug) return;
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      await downloadSheetsWorkbookXlsx(workspaceId, slug, `${slug}.xlsx`);
      setStatus('Downloaded Excel workbook (formulas evaluated)');
    } catch (e) {
      setError(`XLSX export failed: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  };

  const tabs = useMemo(() => parseWorkbookTabs(html), [html]);
  const currentIndex = clampTabIndex(selectedIndex, tabs.length);

  useEffect(() => {
    setTabCount(tabs.length);
  }, [tabs.length, setTabCount]);

  const applyMutation = useCallback(
    async (run: () => Promise<TabMutationResult>, label: string) => {
      if (!workspaceId || !slug) return;
      if (dirtyRef.current) {
        const ok = window.confirm(
          'Unsaved code edits will be replaced by this sheet tab change. Continue?',
        );
        if (!ok) return;
      }
      setMutating(true);
      setError(null);
      setStatus(null);
      try {
        const result = await run();
        if (result.html) {
          setHoldPreview(false);
          setHtml(result.html);
          setPreviewHtml(result.html);
        }
        setSelectedIndex(result.section_index);
        setDirty(false);
        setStatus(`${label} (${result.section_index + 1}/${result.section_count})`);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setMutating(false);
      }
    },
    [workspaceId, slug, setSelectedIndex],
  );

  useEffect(() => {
    if (!workspaceId || !slug) {
      setFilmstrip(null);
      return;
    }
    setFilmstrip({
      workspaceId,
      slug,
      html: holdPreview ? html : previewHtml || html,
      disabled: mutating || loading || !html,
    });
  }, [workspaceId, slug, previewHtml, html, holdPreview, mutating, loading, setFilmstrip]);

  useEffect(() => {
    setReorderOpenWorkbook((fromIndex, toIndex) => {
      if (fromIndex === toIndex) return;
      void applyMutation(
        () => reorderWorkbookTabs(workspaceId, slug, fromIndex, toIndex),
        'Moved sheet tab',
      );
    });
  }, [workspaceId, slug, applyMutation, setReorderOpenWorkbook]);

  useEffect(() => {
    return () => {
      setFilmstrip(null);
      setReorderOpenWorkbook(null);
      setTabCount(0);
    };
  }, [setFilmstrip, setReorderOpenWorkbook, setTabCount]);

  const exportHtml = async () => {
    const live = previewHtml || html;
    if (!live) {
      setError('Workbook is empty; nothing to export.');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      const inlined = await resolveSheetsPreviewAssets(live, workspaceId, slug);
      downloadSheetsHtml(`${slug || 'workbook'}.html`, inlined);
      setStatus('Downloaded self-contained HTML');
    } catch (e) {
      setError(`HTML export failed: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  };

  const scheduleManualSave = useCallback(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveTimer.current = null;
      void saveRef.current();
    }, SHEETS_MANUAL_EDIT_IDLE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, []);

  const onManualEditCommit = useCallback(
    (edits: SheetsTextEdit[]) => {
      if (!Array.isArray(edits) || !edits.length) return;
      const baseline = new Map(
        collectSheetsTextEdits(htmlRef.current).map((edit) => [edit.path, edit.html]),
      );
      const changed = edits.filter((edit) => {
        const before = baseline.get(edit.path);
        if (before === undefined) return false;
        return sanitizeSheetsEditHtml(edit.html) !== sanitizeSheetsEditHtml(before);
      });
      if (!changed.length) return;
      const next = applySheetsTextEdits(htmlRef.current, changed);
      if (next === htmlRef.current) return;
      setHoldPreview(true);
      setHtml(next);
      setDirty(true);
      scheduleManualSave();
    },
    [scheduleManualSave],
  );

  const tabActionsDisabled = mutating || loading || !html;

  const insertSelectedTab = () => {
    const after = tabs.length ? currentIndex : -1;
    void applyMutation(
      () => insertWorkbookTab(workspaceId, slug, after),
      'Inserted sheet tab',
    );
  };

  const duplicateSelectedTab = () => {
    void applyMutation(
      () => duplicateWorkbookTab(workspaceId, slug, currentIndex),
      'Duplicated sheet tab',
    );
  };

  const deleteSelectedTab = () => {
    if (tabs.length <= 1) return;
    if (!window.confirm('Delete the selected sheet tab?')) return;
    void applyMutation(
      () => deleteWorkbookTab(workspaceId, slug, currentIndex),
      'Deleted sheet tab',
    );
  };
  deleteSelectedTabRef.current = deleteSelectedTab;

  const menuBar = (
    <SheetsMenuBar
      onNewWorkbook={() => {
        if (!workspaceId) return;
        void startNewWorkbook(workspaceId, (href) => router.push(href)).catch((e) => {
          setError(sheetsApiErrorMessage((e as Error).message, 'Could not create the workbook.'));
        });
      }}
      onCommit={() => void save()}
      commitDisabled={saving || !dirty || loading}
      onSaveToMyDrive={() => void saveToMyDrive()}
      saveToMyDriveDisabled={savingToDrive || loading || !html}
      onExportXlsx={() => void exportXlsx()}
      onExportHtml={() => void exportHtml()}
      exportDisabled={exporting || loading}
      onInsertTab={insertSelectedTab}
      insertTabDisabled={tabActionsDisabled}
      onDuplicateTab={duplicateSelectedTab}
      duplicateTabDisabled={tabActionsDisabled || !tabs.length}
      onDeleteTab={deleteSelectedTab}
      deleteTabDisabled={tabActionsDisabled || tabs.length <= 1}
      mode={mode}
      onModeChange={(next) => {
        setMode(next);
        if (next !== 'preview') setManualEdit(false);
      }}
      manualEdit={manualEdit}
      onManualEditChange={setManualEdit}
      manualEditDisabled={tabActionsDisabled}
      onRefresh={() => void refresh()}
      refreshDisabled={loading || refreshing}
      trailing={
        status || dirty || saving || savingToDrive || refreshing ? (
          <div className="ml-2 flex items-center gap-2 border-l border-border pl-2">
            {status && (
              <span className="max-w-[28rem] truncate text-xs text-muted-foreground" title={status}>
                {status}
              </span>
            )}
            {dirty && <span className="text-xs text-amber-600">Unsaved</span>}
            {(saving || savingToDrive || refreshing) && (
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
          title={title || 'Sheets'}
          subtitle={slug ? `sheets/${slug}/workbook.html` : undefined}
          nav={menuBar}
        />
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading workbook…
        </div>
        <SheetsStatusBar />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header
        title={title}
        subtitle={`JSON grid in workbook.html · Export to Excel for sharing`}
        nav={menuBar}
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      {agentWriting && (
        <div className="border-b border-workspace-accent/20 bg-workspace-accent-10 px-4 py-2 text-xs text-foreground">
          Abi is updating the workbook…
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
            : `Sheets runtime degraded: ${runtimeDetail || 'Sidecar not ready; Abi falls back to Forgejo.'}`}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col">
        <div className="relative min-h-0 flex-1">
        {/* Keep iframe mounted so preview stays warm when switching Code ↔ Preview. */}
        <div
          className={cn(
            'absolute inset-0',
            mode !== 'preview' && 'invisible pointer-events-none',
          )}
          aria-hidden={mode !== 'preview'}
        >
          <SheetsPreviewFrame
            html={previewHtml}
            workspaceId={workspaceId}
            slug={slug}
            selectedIndex={currentIndex}
            onSelectedIndexChange={setSelectedIndex}
            manualEdit={manualEdit}
            onManualEditCommit={onManualEditCommit}
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
                setHoldPreview(false);
                setHtml(value ?? '');
                setDirty(true);
              }}
              onMount={(editor, monaco) => {
                // Override Monaco save / browser-reload chords for Sheets.
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
      </div>

      <SheetsStatusBar onRefresh={() => void refresh()} refreshing={refreshing} />
    </div>
  );
}
