'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { MonacoEditor } from '@/components/monaco/monaco-editor';
import { Header } from '@/components/shell/header';
import {
  isDocumentsTypingTarget,
  DocumentsMenuBar,
  type DocumentsEditorMode,
} from '@/components/documents/documents-menu-bar';
import {
  DocumentsPreviewFrame,
  type DocumentsPreviewFrameHandle,
} from '@/components/documents/documents-preview-frame';
import { downloadDocumentsHtml, resolveDocumentsPreviewAssets } from '@/components/documents/documents-assets';
import {
  applyDocumentsTextEdits,
  collectDocumentsTextEdits,
  sanitizeDocumentsEditHtml,
  DOCUMENTS_MANUAL_EDIT_IDLE_MS,
  type DocumentsTextEdit,
} from '@/components/documents/documents-preview-fit';
import {
  clampSectionIndex,
  deleteSection,
  duplicateSection,
  applyDocumentCommands,
  parseDocumentsHeadingOutline,
  parseDocumentsOutline,
  parseDocumentsSectionOutline,
  reorderSections,
  type DocumentsInsertKind,
  type SectionMutationResult,
} from '@/components/documents/documents-outline';
import { DocumentsStatusBar } from '@/components/documents/documents-status-bar';
import {
  openDocumentsAgentPane,
  documentsApiErrorMessage,
} from '@/lib/create-documents-project';
import { OfficeCreateLoader } from '@/components/office/office-create-loader';
import { officeCreateHref } from '@/components/office/office-create';
import { copyDocumentToMyDrive } from '@/lib/documents-my-drive';
import { authFetch } from '@/stores/auth';
import {
  DOCUMENTS_UPDATED_EVENT,
  useDocumentsStore,
  type DocumentsUpdatedDetail,
} from '@/stores/documents';
import { cn } from '@/lib/utils';

function isGitWriteRaceDetail(detail: string): boolean {
  const lowered = detail.toLowerCase();
  return (
    lowered.includes('pushrejected') ||
    lowered.includes('cannot lock ref') ||
    lowered.includes('but expected') ||
    lowered.includes('git write raced') ||
    lowered.includes('document sync raced') ||
    lowered.includes('document branch sync raced')
  );
}

function friendlyRuntimeDetail(detail: string | null | undefined): string | null {
  if (!detail) return null;
  const trimmed = detail.trim();
  if (!trimmed) return null;
  if (isGitWriteRaceDetail(trimmed)) {
    return 'Document branch sync raced; retry open or save. Abi can still edit via Forgejo.';
  }
  if (trimmed.startsWith('{') || trimmed.includes('"validations"')) {
    return 'Reconnecting to existing runtime…';
  }
  if (trimmed.toLowerCase().includes('already exists')) {
    return 'Reconnecting to existing runtime…';
  }
  return trimmed;
}

async function ensureDocumentsRuntime(
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
      `/api/documents/projects/${encodeURIComponent(slug)}/runtime?workspace_id=${encodeURIComponent(workspaceId)}`,
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

export default function SectionsEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const slug = typeof params?.slug === 'string' ? params.slug : '';
  const setSelectedSlug = useDocumentsStore((s) => s.setSelectedSlug);
  const setSelectedTitle = useDocumentsStore((s) => s.setSelectedTitle);
  const selectedIndex = useDocumentsStore((s) => s.selectedIndex);
  const setSelectedIndex = useDocumentsStore((s) => s.setSelectedIndex);
  const setSectionCount = useDocumentsStore((s) => s.setSectionCount);
  const setOutline = useDocumentsStore((s) => s.setOutline);
  const setReorderOpenDocument = useDocumentsStore((s) => s.setReorderOpenDocument);
  const setEditorMode = useDocumentsStore((s) => s.setEditorMode);
  const setRuntimeStatus = useDocumentsStore((s) => s.setRuntimeStatus);
  const setRuntimeMeta = useDocumentsStore((s) => s.setRuntimeMeta);
  const setDocumentDirty = useDocumentsStore((s) => s.setDocumentDirty);
  const setDocumentSource = useDocumentsStore((s) => s.setDocumentSource);
  const runtimeStatus = useDocumentsStore((s) => s.runtimeStatus);
  const runtimeDetail = useDocumentsStore((s) => s.runtimeDetail);
  const refreshToken = useDocumentsStore((s) => s.refreshToken);
  const agentWriting = useDocumentsStore((s) => s.agentWriting);

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
  const [mode, setMode] = useState<DocumentsEditorMode>('preview');
  const [manualEdit, setManualEdit] = useState(false);
  const [holdPreview, setHoldPreview] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [creating, setCreating] = useState(false);
  const previewRef = useRef<DocumentsPreviewFrameHandle>(null);
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
    openDocumentsAgentPane({ slug });
  }, [slug]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [slug, setSelectedIndex]);

  useEffect(() => {
    dirtyRef.current = dirty;
    setDocumentDirty(dirty);
  }, [dirty, setDocumentDirty]);

  useEffect(() => {
    htmlRef.current = html;
  }, [html]);

  useEffect(() => {
    manualEditRef.current = manualEdit;
  }, [manualEdit]);

  useEffect(() => {
    return () => {
      useDocumentsStore.getState().setDocumentDirty(false);
      useDocumentsStore.getState().setDocumentSource(null);
    };
  }, []);

  const applyRuntime = useCallback(
    (runtime: Awaited<ReturnType<typeof ensureDocumentsRuntime>>) => {
      setRuntimeMeta({
        forgejoBranch: runtime.branch ?? (slug ? `documents/${slug}` : null),
        coderWorkspace: runtime.coder_workspace ?? (slug ? `sections-${slug}` : null),
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

  const loadDocument = useCallback(
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
        const [projRes, documentRes] = await Promise.all([
          authFetch(
            `/api/documents/projects/${encodeURIComponent(slug)}?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
          authFetch(
            `/api/documents/projects/${encodeURIComponent(slug)}/document?workspace_id=${encodeURIComponent(workspaceId)}&_=${Date.now()}`,
            { cache: 'no-store' },
          ),
        ]);
        if (gen !== loadGenRef.current) return;
        if (!projRes.ok || !documentRes.ok) {
          const body = (await (projRes.ok ? documentRes : projRes)
            .json()
            .catch(() => ({}))) as { detail?: unknown };
          throw new Error(documentsApiErrorMessage(body.detail, 'Failed to load document'));
        }
        const proj = (await projRes.json()) as {
          title: string;
          branch?: string;
        };
        const document = (await documentRes.json()) as { html: string; source?: string };
        if (gen !== loadGenRef.current) return;
        setTitle(proj.title);
        setHoldPreview(false);
        setHtml(document.html);
        setPreviewHtml(document.html);
        setSelectedIndex(
          clampSectionIndex(
            useDocumentsStore.getState().selectedIndex,
            parseDocumentsOutline(document.html).length,
          ),
        );
        setDirty(false);
        setDocumentSource(
          document.source === 'sidecar' || document.source === 'forgejo' ? document.source : null,
        );
        setSelectedSlug(slug);
        setSelectedTitle(proj.title);
        setRuntimeMeta({
          forgejoBranch: proj.branch || `documents/${slug}`,
          coderWorkspace: `sections-${slug}`,
        });
        if (quiet) {
          const src =
            document.source === 'sidecar'
              ? 'workspace'
              : document.source === 'forgejo'
                ? 'Forgejo snapshot'
                : null;
          setStatus(src ? `Preview refreshed (${src})` : 'Preview refreshed');
        }
        setLoading(false);
        setRefreshing(false);
        if (ensureRuntime) {
          const runtime = await ensureDocumentsRuntime(workspaceId, slug, quiet ? 2 : 6);
          if (gen !== loadGenRef.current) return;
          applyRuntime(runtime);
        }
      } catch (e) {
        if (gen !== loadGenRef.current) return;
        const message = (e as Error).message;
        // Document load Forgejo races are not a Coder outage; keep banners separate.
        setError(
          isGitWriteRaceDetail(message)
            ? 'Document sync raced on Forgejo; refresh to retry.'
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
      setDocumentSource,
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
    await loadDocument({ quiet: true, ensureRuntime: true });
  }, [loadDocument]);

  useEffect(() => {
    void loadDocument({ quiet: false, ensureRuntime: true });
  }, [loadDocument]);

  // Auto-refresh when Abi (or store) bumps refreshToken after a sections write tool.
  useEffect(() => {
    if (skipTokenEffectRef.current) {
      skipTokenEffectRef.current = false;
      return;
    }
    if (!refreshToken) return;
    if (dirtyRef.current) {
      setStatus('Document updated on server (unsaved local edits kept; use View → Refresh)');
      return;
    }
    void loadDocument({ quiet: true, ensureRuntime: false });
  }, [refreshToken, loadDocument]);

  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<DocumentsUpdatedDetail>).detail;
      if (detail?.slug && detail.slug !== slug) return;
      useDocumentsStore.getState().requestDocumentRefresh(detail?.slug ?? slug);
    };
    window.addEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(DOCUMENTS_UPDATED_EVENT, onUpdated);
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
    const document = htmlRef.current;
    if (!workspaceId || !slug || !document) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const res = await authFetch(`/api/documents/projects/${encodeURIComponent(slug)}/document`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          html: document,
          message: `chore(document): update ${slug}`,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
        throw new Error(documentsApiErrorMessage(body.detail, `Save failed (${res.status})`));
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
      const { relativePath } = await copyDocumentToMyDrive({
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

  const deleteSelectedSectionRef = useRef<() => void>(() => {});

  // ⌘/Ctrl+S Save, ⌘/Ctrl+R Refresh (intercept browser reload). Delete section when not typing.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      if (!mod) {
        if (
          event.key === 'Delete' &&
          !manualEditRef.current &&
          !isDocumentsTypingTarget(event.target)
        ) {
          event.preventDefault();
          deleteSelectedSectionRef.current();
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

  const exportPptx = async () => {
    // Preview iframe stays mounted (hidden in Code mode) so export stays available.
    // Export goes through postMessage; sandbox omits allow-same-origin.
    if (!previewRef.current) {
      setError('Preview is not ready for PDF export.');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      await previewRef.current.exportPptx();
      setStatus(
        'PDF started from live HTML (closest fit; fonts and wrap will differ from preview)',
      );
    } catch (e) {
      setError(`PDF export failed: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  };

  const exportPdf = async () => {
    if (!previewRef.current) {
      setError('Preview is not ready for PDF export.');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      await previewRef.current.exportPdf();
    } catch (e) {
      setError(`PDF export failed: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  };

  const sections = useMemo(() => parseDocumentsOutline(html), [html]);
  const sectionBlocks = useMemo(() => parseDocumentsSectionOutline(html), [html]);
  const currentIndex = clampSectionIndex(selectedIndex, sections.length);
  const pageMutationsAligned = sections.length === sectionBlocks.length;

  // Publish the section count so the chat pane can tell Abi "section N of M".
  useEffect(() => {
    setSectionCount(sections.length);
  }, [sections.length, setSectionCount]);

  const applyMutation = useCallback(
    async (run: () => Promise<SectionMutationResult>, label: string) => {
      if (!workspaceId || !slug) return;
      if (dirtyRef.current) {
        const ok = window.confirm(
          'Unsaved code edits will be replaced by this page change. Continue?',
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
      setOutline(null);
      return;
    }
    setOutline({
      workspaceId,
      slug,
      html: holdPreview ? html : previewHtml || html,
      disabled: mutating || loading || !html,
    });
  }, [workspaceId, slug, previewHtml, html, holdPreview, mutating, loading, setOutline]);

  useEffect(() => {
    setReorderOpenDocument((fromIndex, toIndex) => {
      if (fromIndex === toIndex) return;
      const source = htmlRef.current;
      if (
        parseDocumentsHeadingOutline(source).length !==
        parseDocumentsSectionOutline(source).length
      ) {
        return;
      }
      void applyMutation(
        () => reorderSections(workspaceId, slug, fromIndex, toIndex),
        'Moved page',
      );
    });
  }, [workspaceId, slug, applyMutation, setReorderOpenDocument]);

  useEffect(() => {
    return () => {
      setOutline(null);
      setReorderOpenDocument(null);
      setSectionCount(0);
    };
  }, [setOutline, setReorderOpenDocument, setSectionCount]);

  const exportHtml = async () => {
    const live = previewHtml || html;
    if (!live) {
      setError('Document is empty; nothing to export.');
      return;
    }
    setExporting(true);
    setError(null);
    setStatus(null);
    try {
      const inlined = await resolveDocumentsPreviewAssets(live, workspaceId, slug);
      downloadDocumentsHtml(`${slug || 'document'}.html`, inlined);
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
    }, DOCUMENTS_MANUAL_EDIT_IDLE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, []);

  const onManualEditCommit = useCallback(
    (edits: DocumentsTextEdit[]) => {
      if (!Array.isArray(edits) || !edits.length) return;
      const baseline = new Map(
        collectDocumentsTextEdits(htmlRef.current).map((edit) => [edit.path, edit.html]),
      );
      const changed = edits.filter((edit) => {
        const before = baseline.get(edit.path);
        if (before === undefined) return false;
        return sanitizeDocumentsEditHtml(edit.html) !== sanitizeDocumentsEditHtml(before);
      });
      if (!changed.length) return;
      const next = applyDocumentsTextEdits(htmlRef.current, changed);
      if (next === htmlRef.current) return;
      setHoldPreview(true);
      setHtml(next);
      setDirty(true);
      scheduleManualSave();
    },
    [scheduleManualSave],
  );

  const sectionActionsDisabled = mutating || loading || !html;

  const insertBlock = (kind: DocumentsInsertKind) => {
    const after = sections.length ? currentIndex : -1;
    const request =
      kind === 'page-break'
        ? { type: 'insert_page_break' as const, after_heading: after }
        : kind === 'heading'
          ? { type: 'insert_heading' as const, after_heading: after, title: 'Heading', level: 2 }
          : { type: 'insert_paragraph' as const, after_heading: after, text: '' };
    const label =
      kind === 'page-break'
        ? 'Inserted page break'
        : kind === 'heading'
          ? 'Inserted heading'
          : 'Inserted paragraph';
    void applyMutation(() => applyDocumentCommands(workspaceId, slug, [request]), label);
  };

  const duplicateSelectedSection = () => {
    const sectionIndex = clampSectionIndex(
      currentIndex,
      parseDocumentsSectionOutline(htmlRef.current).length,
    );
    void applyMutation(
      () => duplicateSection(workspaceId, slug, sectionIndex),
      'Duplicated page',
    );
  };

  const deleteSelectedSection = () => {
    const sectionCount = parseDocumentsSectionOutline(htmlRef.current).length;
    if (sectionCount <= 1) return;
    if (!window.confirm('Delete the selected page?')) return;
    const sectionIndex = clampSectionIndex(currentIndex, sectionCount);
    void applyMutation(
      () => deleteSection(workspaceId, slug, sectionIndex),
      'Deleted page',
    );
  };
  deleteSelectedSectionRef.current = deleteSelectedSection;

  const menuBar = (
    <DocumentsMenuBar
      onNewPresentation={() => {
        if (!workspaceId || creating) return;
        setCreating(true);
        router.push(officeCreateHref('document', workspaceId));
      }}
      newDisabled={creating}
      onCommit={() => void save()}
      commitDisabled={saving || !dirty || loading}
      onSaveToMyDrive={() => void saveToMyDrive()}
      saveToMyDriveDisabled={savingToDrive || loading || !html}
      onExportPdf={() => void exportPdf()}
      onExportPptx={() => void exportPptx()}
      onExportHtml={() => void exportHtml()}
      exportDisabled={exporting || loading}
      onInsert={insertBlock}
      insertSectionDisabled={sectionActionsDisabled}
      onDuplicateSection={duplicateSelectedSection}
      duplicateSectionDisabled={
        sectionActionsDisabled || !sectionBlocks.length || !pageMutationsAligned
      }
      onDeleteSection={deleteSelectedSection}
      deleteSectionDisabled={
        sectionActionsDisabled || sectionBlocks.length <= 1 || !pageMutationsAligned
      }
      mode={mode}
      onModeChange={(next) => {
        setMode(next);
        if (next !== 'preview') setManualEdit(false);
      }}
      manualEdit={manualEdit}
      onManualEditChange={setManualEdit}
      manualEditDisabled={sectionActionsDisabled}
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

  if (creating) {
    return (
      <div className="flex h-full flex-col">
        <Header title="New document" nav={menuBar} />
        <OfficeCreateLoader kind="document" phase="creating" />
        <DocumentsStatusBar />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full flex-col">
        <Header
          title={title || 'Documents'}
          subtitle={slug ? `documents/${slug}/document.html` : undefined}
          nav={menuBar}
        />
        <OfficeCreateLoader kind="document" phase="opening" />
        <DocumentsStatusBar />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header
        title={title}
        subtitle={`HTML source · letter pages (8.5 x 11 in)`}
        nav={menuBar}
      />

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      {agentWriting && (
        <div className="border-b border-workspace-accent/20 bg-workspace-accent-10 px-4 py-2 text-xs text-foreground">
          Abi is updating the document…
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
            : `Documents runtime degraded: ${runtimeDetail || 'Sidecar not ready; Abi falls back to Forgejo.'}`}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col">
        <div className="relative min-h-0 flex-1">
        {/* Keep iframe mounted so PDF export and live preview stay warm. */}
        <div
          className={cn(
            'absolute inset-0',
            mode !== 'preview' && 'invisible pointer-events-none',
          )}
          aria-hidden={mode !== 'preview'}
        >
          <DocumentsPreviewFrame
            ref={previewRef}
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
                // Override Monaco save / browser-reload chords for Documents.
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

      <DocumentsStatusBar onRefresh={() => void refresh()} refreshing={refreshing} />
    </div>
  );
}
