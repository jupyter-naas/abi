'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  GitBranch,
  History,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  Send,
  Stethoscope,
  X,
} from 'lucide-react';
import { MonacoEditor } from '@/components/monaco/monaco-editor';
import { Header } from '@/components/shell/header';
import { AppFileTree } from '@/components/apps-builder/app-file-tree';
import { AppPreviewFrame } from '@/components/apps-builder/app-preview-frame';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import {
  appEditorPath,
  appProjectsApi,
  languageForPath,
  previewUrl,
  type AppProject,
  type AppProjectCommit,
  type AppProjectIssue,
  type AppSubmitConfig,
} from '@/lib/app-projects';
import { getApiUrl } from '@/lib/config';
import { openFeatureAgentPane } from '@/lib/feature-agent-pane';
import { cn } from '@/lib/utils';
import { APP_PROJECT_UPDATED_EVENT, useAppProjectsStore } from '@/stores/app-projects';
import { usePublishFeatureResource } from '@/stores/feature-pane';

const WRITE_DEBOUNCE_MS = 400;
const MAX_PREVIEW_ERRORS = 5;

type Buffer = { content: string; binary: boolean; size: number };

function appsHome(workspaceId: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/apps`;
}

export default function AppEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const slug = typeof params?.slug === 'string' ? params.slug : '';
  const { prompt, dialog: promptDialog } = usePrompt();
  const { confirm, dialog: confirmDialog } = useConfirm();
  const agentWriting = useAppProjectsStore((s) => s.agentWriting);

  const [project, setProject] = useState<AppProject | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [openPath, setOpenPath] = useState<string | null>(null);
  const [buffers, setBuffers] = useState<Record<string, Buffer>>({});
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [previewErrors, setPreviewErrors] = useState<string[]>([]);
  const [issues, setIssues] = useState<AppProjectIssue[] | null>(null);
  const [history, setHistory] = useState<AppProjectCommit[] | null>(null);
  const [submitConfig, setSubmitConfig] = useState<AppSubmitConfig | null>(null);
  const [codeWidth, setCodeWidth] = useState(50);

  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const buffersRef = useRef(buffers);
  buffersRef.current = buffers;
  const pendingRef = useRef(pending);
  pendingRef.current = pending;
  const saveRef = useRef<() => Promise<void>>(async () => {});
  const splitRef = useRef<HTMLDivElement>(null);

  // The pane binds the Apps agent; its builder tools default to this project
  // and see the preview's runtime errors.
  usePublishFeatureResource(
    project
      ? {
          feature: 'apps',
          kind: 'app_project',
          id: project.slug,
          label: project.title,
          errors: previewErrors,
        }
      : null,
  );

  useEffect(() => {
    if (slug) openFeatureAgentPane('apps', { resourceId: slug });
  }, [slug]);

  const loadFile = useCallback(
    async (path: string, { force = false } = {}) => {
      if (!force && buffersRef.current[path]) return;
      try {
        const file = await appProjectsApi.readFile(workspaceId, slug, path);
        setBuffers((prev) => ({
          ...prev,
          [path]: { content: file.content ?? '', binary: file.binary, size: file.size },
        }));
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [workspaceId, slug],
  );

  const refreshProject = useCallback(async () => {
    const next = await appProjectsApi.get(workspaceId, slug);
    setProject(next);
    return next;
  }, [workspaceId, slug]);

  const mintPreview = useCallback(async () => {
    try {
      const token = await appProjectsApi.previewToken(workspaceId, slug);
      setPreviewPath(token.path);
      return token.expires_in;
    } catch (e) {
      setError(`Preview unavailable: ${(e as Error).message}`);
      return null;
    }
  }, [workspaceId, slug]);

  // Load the project, open its entry page, mint the preview link.
  useEffect(() => {
    if (!workspaceId || !slug) return;
    let cancelled = false;
    setLoadError(null);
    setBuffers({});
    (async () => {
      try {
        const loaded = await appProjectsApi.get(workspaceId, slug);
        if (cancelled) return;
        setProject(loaded);
        const first =
          loaded.entry ?? loaded.files.find((f) => f.path === 'manifest.json')?.path ?? loaded.files[0]?.path;
        if (first) {
          setOpenPath(first);
          void loadFile(first, { force: true });
        }
      } catch (e) {
        if (!cancelled) setLoadError((e as Error).message);
      }
    })();
    appProjectsApi.submitConfig().then(setSubmitConfig).catch(() => setSubmitConfig(null));
    return () => {
      cancelled = true;
    };
  }, [workspaceId, slug, loadFile]);

  // Preview tokens expire: re-mint before they do.
  useEffect(() => {
    if (!project) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    const tick = async () => {
      const expiresIn = await mintPreview();
      if (stopped) return;
      const next = Math.max(60, Math.floor((expiresIn ?? 600) * 0.8)) * 1000;
      timer = setTimeout(() => void tick(), next);
    };
    void tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
    // Mint once per project, not on every project refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.slug, mintPreview]);

  const flushWrite = useCallback(
    async (path: string) => {
      const timer = timers.current[path];
      if (timer) clearTimeout(timer);
      delete timers.current[path];
      const buffer = buffersRef.current[path];
      if (!buffer || buffer.binary) return;
      try {
        await appProjectsApi.writeFile(workspaceId, slug, path, buffer.content);
        setPending((prev) => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
        setProject((prev) => (prev ? { ...prev, dirty: true } : prev));
        setPreviewVersion((v) => v + 1);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [workspaceId, slug],
  );

  const flushAll = useCallback(async () => {
    await Promise.all([...pendingRef.current].map((path) => flushWrite(path)));
  }, [flushWrite]);

  const onEdit = (value: string | undefined) => {
    if (!openPath) return;
    const path = openPath;
    setBuffers((prev) => ({
      ...prev,
      [path]: { ...(prev[path] ?? { binary: false, size: 0 }), content: value ?? '' },
    }));
    setPending((prev) => new Set(prev).add(path));
    const timer = timers.current[path];
    if (timer) clearTimeout(timer);
    timers.current[path] = setTimeout(() => void flushWrite(path), WRITE_DEBOUNCE_MS);
  };

  // The Apps agent changed the project: reload files and the preview.
  useEffect(() => {
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ slug?: string }>).detail;
      if (detail?.slug && detail.slug !== slug) return;
      void (async () => {
        try {
          const next = await refreshProject();
          const paths = new Set(next.files.map((f) => f.path));
          setBuffers((prev) => {
            const kept: Record<string, Buffer> = {};
            for (const [path, buffer] of Object.entries(prev)) {
              // Keep unsynced local typing; drop the rest so it reloads.
              if (pendingRef.current.has(path) && paths.has(path)) kept[path] = buffer;
            }
            return kept;
          });
          if (openPath && paths.has(openPath) && !pendingRef.current.has(openPath)) {
            void loadFile(openPath, { force: true });
          } else if (openPath && !paths.has(openPath)) {
            setOpenPath(next.entry ?? next.files[0]?.path ?? null);
          }
          setPreviewVersion((v) => v + 1);
          setStatus('Updated by the Apps agent');
        } catch (e) {
          setError((e as Error).message);
        }
      })();
    };
    window.addEventListener(APP_PROJECT_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(APP_PROJECT_UPDATED_EVENT, onUpdated);
  }, [slug, openPath, refreshProject, loadFile]);

  const selectFile = (path: string) => {
    setOpenPath(path);
    void loadFile(path);
  };

  const save = useCallback(async () => {
    if (!project) return;
    setBusy('save');
    setError(null);
    try {
      await flushAll();
      const result = await appProjectsApi.save(workspaceId, slug);
      setStatus(result.saved && result.commit ? `Saved ${result.commit.sha.slice(0, 7)}` : 'Nothing to save');
      await refreshProject();
      if (history) setHistory(await appProjectsApi.history(workspaceId, slug));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [project, flushAll, workspaceId, slug, refreshProject, history]);
  saveRef.current = save;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void saveRef.current();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  useEffect(
    () => () => {
      for (const timer of Object.values(timers.current)) clearTimeout(timer);
    },
    [],
  );

  const createFile = async () => {
    const path = await prompt({
      title: 'New file',
      description: 'Path inside the app, e.g. js/chart.js or pages/about.html',
      placeholder: 'js/chart.js',
      confirmLabel: 'Create',
    });
    if (!path) return;
    try {
      const written = await appProjectsApi.writeFile(workspaceId, slug, path.trim(), '');
      await refreshProject();
      setOpenPath(written.path);
      setBuffers((prev) => ({ ...prev, [written.path]: { content: '', binary: false, size: 0 } }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const deleteFile = async (path: string) => {
    if (!(await confirm({ title: `Delete ${path}?`, confirmLabel: 'Delete', destructive: true }))) return;
    try {
      await appProjectsApi.deleteFile(workspaceId, slug, path);
      setBuffers((prev) => {
        const next = { ...prev };
        delete next[path];
        return next;
      });
      const next = await refreshProject();
      if (openPath === path) setOpenPath(next.entry ?? next.files[0]?.path ?? null);
      setPreviewVersion((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const discard = async () => {
    const ok = await confirm({
      title: 'Discard unsaved changes?',
      description: 'The app goes back to its last saved version, for everyone in the workspace.',
      confirmLabel: 'Discard',
      destructive: true,
    });
    if (!ok) return;
    try {
      for (const timer of Object.values(timers.current)) clearTimeout(timer);
      timers.current = {};
      setPending(new Set());
      const next = await appProjectsApi.discard(workspaceId, slug);
      setProject(next);
      setBuffers({});
      const path = openPath && next.files.some((f) => f.path === openPath) ? openPath : next.entry;
      setOpenPath(path);
      if (path) void loadFile(path, { force: true });
      setPreviewVersion((v) => v + 1);
      setStatus('Changes discarded');
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const runCheck = async () => {
    setBusy('check');
    try {
      await flushAll();
      setIssues(await appProjectsApi.check(workspaceId, slug));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const toggleHistory = async () => {
    if (history) {
      setHistory(null);
      return;
    }
    try {
      setHistory(await appProjectsApi.history(workspaceId, slug));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const submit = async () => {
    if (!project || !submitConfig?.configured) return;
    let targetModule: string | undefined;
    if (!project.origin?.repo_path) {
      const choice = await prompt({
        title: 'Submit to the source repository',
        description: `Module that will hold this new app (${submitConfig.modules.join(', ')}).`,
        defaultValue: submitConfig.default_module ?? submitConfig.modules[0] ?? '',
        confirmLabel: 'Submit',
      });
      if (!choice) return;
      targetModule = choice.trim();
    } else {
      const ok = await confirm({
        title: `Submit ${project.title} for review?`,
        description: `Saves, then creates a branch in ${submitConfig.repo} with the changes to ${project.origin.repo_path}. Nothing goes live until the tech team merges it.`,
        confirmLabel: 'Submit',
        destructive: false,
      });
      if (!ok) return;
    }
    setBusy('submit');
    setError(null);
    try {
      await flushAll();
      const submission = await appProjectsApi.submit(workspaceId, slug, targetModule);
      await refreshProject();
      setStatus(`Submitted as ${submission.branch}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const onPointerDown = (event: React.PointerEvent) => {
    event.preventDefault();
    const container = splitRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const move = (e: PointerEvent) => {
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setCodeWidth(Math.min(75, Math.max(25, pct)));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      document.body.style.removeProperty('user-select');
    };
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const openBuffer = openPath ? buffers[openPath] : undefined;
  const src = useMemo(
    () => (previewPath ? previewUrl(getApiUrl(), previewPath) : null),
    [previewPath],
  );
  const unsaved = Boolean(project?.dirty) || pending.size > 0;
  const submitTitle = !submitConfig?.configured
    ? 'Submitting to the source repository is not configured on this platform'
    : project?.origin?.repo_path
      ? `Open a review branch in ${submitConfig.repo} for ${project.origin.repo_path}`
      : `Open a review branch in ${submitConfig.repo}`;

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <Header title="App" />
        <AlertTriangle size={32} className="text-amber-500" />
        <p className="text-sm text-muted-foreground">{loadError}</p>
        <button
          type="button"
          onClick={() => router.push(appsHome(workspaceId))}
          className="text-sm font-medium text-workspace-accent hover:underline"
        >
          Back to apps
        </button>
      </div>
    );
  }

  const menuBtn = (label: string, onClick: () => void, icon: React.ReactNode, opts: { disabled?: boolean; title?: string; primary?: boolean } = {}) => (
    <button
      type="button"
      onClick={onClick}
      disabled={opts.disabled}
      title={opts.title ?? label}
      className={cn(
        'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        opts.primary
          ? 'bg-workspace-accent text-white hover:bg-workspace-accent/90'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {icon}
      {label}
    </button>
  );

  const menuBar = (
    <div className="flex min-w-0 flex-wrap items-center gap-1">
      <button
        type="button"
        onClick={() => router.push(appsHome(workspaceId))}
        title="Back to apps"
        className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <ArrowLeft size={14} />
      </button>
      {menuBtn('Save', () => void save(), busy === 'save' ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />, {
        disabled: !project || busy !== null,
        title: 'Save (⌘S): one commit with every change',
        primary: unsaved,
      })}
      {menuBtn('Discard', () => void discard(), <RotateCcw size={13} />, { disabled: !project?.dirty || busy !== null })}
      {menuBtn('Check', () => void runCheck(), busy === 'check' ? <Loader2 size={13} className="animate-spin" /> : <Stethoscope size={13} />, { disabled: !project })}
      {menuBtn('History', () => void toggleHistory(), <History size={13} />, { disabled: !project })}
      {menuBtn('Submit', () => void submit(), busy === 'submit' ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />, {
        disabled: !project || !submitConfig?.configured || busy !== null,
        title: submitTitle,
      })}
      {menuBtn('New app', async () => {
        const title = await prompt({ title: 'New app', placeholder: 'Budget tracker', confirmLabel: 'Create' });
        if (!title) return;
        try {
          const created = await appProjectsApi.create(workspaceId, title.trim());
          router.push(appEditorPath(workspaceId, created.slug));
        } catch (e) {
          setError((e as Error).message);
        }
      }, <Plus size={13} />)}
      <div className="ml-2 flex min-w-0 items-center gap-2 border-l border-border pl-2 text-xs">
        {project?.branch && (
          <span className="flex items-center gap-1 truncate text-muted-foreground" title={`${project.repo_id} · ${project.branch}`}>
            <GitBranch size={12} /> {project.branch}
          </span>
        )}
        {unsaved && <span className="text-amber-600">Unsaved</span>}
        {status && <span className="max-w-[20rem] truncate text-muted-foreground" title={status}>{status}</span>}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <Header
        title={project ? `${project.icon_emoji ? `${project.icon_emoji} ` : ''}${project.title}` : 'App'}
        subtitle={project?.origin ? `Copy of ${project.origin.app_id}` : 'App project'}
        nav={menuBar}
      />
      {promptDialog}
      {confirmDialog}

      {error && (
        <div className="flex items-start gap-2 border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError(null)} title="Dismiss">
            <X size={12} />
          </button>
        </div>
      )}
      {agentWriting && (
        <div className="border-b border-workspace-accent/20 bg-workspace-accent-10 px-4 py-2 text-xs text-foreground">
          The Apps agent is editing this app…
        </div>
      )}
      {project?.origin?.kind === 'external' && (
        <div className="border-b border-border/60 bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          This app is published as its own site{project.origin.url ? ` (${project.origin.url})` : ''}. The preview
          shows its static files; server functions and sign-in do not run here.
        </div>
      )}
      {project?.submission && (
        <div className="border-b border-border/60 bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          Submitted for review as{' '}
          <a
            href={project.submission.pull_request_url ?? project.submission.url ?? '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-workspace-accent hover:underline"
          >
            {project.submission.branch}
          </a>
          {project.submission.target_path ? ` → ${project.submission.target_path}` : ''}.
        </div>
      )}

      {!project ? (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading app…
        </div>
      ) : (
        <div ref={splitRef} className="flex min-h-0 flex-1">
          {/* Left: code */}
          <div className="flex min-w-0" style={{ width: `${codeWidth}%` }}>
            <div className="w-44 shrink-0">
              <AppFileTree
                files={project.files}
                selected={openPath}
                dirtyPaths={pending}
                entry={project.entry}
                onSelect={selectFile}
                onCreate={() => void createFile()}
                onDelete={(path) => void deleteFile(path)}
              />
            </div>
            <div className="relative flex min-w-0 flex-1 flex-col">
              <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-xs">
                <span className="truncate font-medium text-foreground">{openPath ?? 'No file open'}</span>
                {openPath && pending.has(openPath) && <Loader2 size={11} className="animate-spin text-muted-foreground" />}
              </div>
              {history && (
                <div className="max-h-48 overflow-auto border-b border-border bg-muted/30 px-3 py-2 text-xs">
                  {history.map((c) => (
                    <div key={c.sha} className="flex gap-2 py-0.5">
                      <code className="text-muted-foreground">{c.sha.slice(0, 7)}</code>
                      <span className="flex-1 truncate">{c.message}</span>
                      <span className="text-muted-foreground">{c.author}</span>
                    </div>
                  ))}
                </div>
              )}
              {issues && (
                <div className="max-h-48 overflow-auto border-b border-border bg-muted/30 px-3 py-2 text-xs">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="font-semibold">Check</span>
                    <button type="button" onClick={() => setIssues(null)} title="Close">
                      <X size={12} />
                    </button>
                  </div>
                  {issues.length === 0 && previewErrors.length === 0 ? (
                    <p className="flex items-center gap-1 text-emerald-600">
                      <CheckCircle2 size={12} /> No problems found.
                    </p>
                  ) : (
                    issues.map((issue, i) => (
                      <p
                        key={i}
                        className={cn(
                          issue.level === 'error' && 'text-red-600',
                          issue.level === 'warning' && 'text-amber-600',
                          issue.level === 'info' && 'text-muted-foreground',
                        )}
                      >
                        {issue.path ? <code className="mr-1">{issue.path}</code> : null}
                        {issue.message}
                      </p>
                    ))
                  )}
                </div>
              )}
              <div className="min-h-0 flex-1">
                {!openPath ? (
                  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                    Pick a file on the left.
                  </div>
                ) : !openBuffer ? (
                  <div className="flex h-full items-center justify-center gap-2 text-xs text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" /> Opening {openPath}…
                  </div>
                ) : openBuffer.binary ? (
                  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                    Binary file ({openBuffer.size} bytes): not editable here.
                  </div>
                ) : (
                  <MonacoEditor
                    path={openPath}
                    language={languageForPath(openPath)}
                    value={openBuffer.content}
                    onChange={onEdit}
                    onMount={(editor, monaco) => {
                      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
                        void saveRef.current();
                      });
                    }}
                  />
                )}
              </div>
            </div>
          </div>

          <div
            role="separator"
            aria-orientation="vertical"
            onPointerDown={onPointerDown}
            className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-workspace-accent/50"
          />

          {/* Middle: the app, live. The Apps agent is the right pane. */}
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">
              <AppPreviewFrame
                src={src}
                version={previewVersion}
                title={project.title}
                onLoadStart={() => setPreviewErrors([])}
                onError={(message) =>
                  setPreviewErrors((prev) => [...prev, message].slice(-MAX_PREVIEW_ERRORS))
                }
              />
            </div>
            {previewErrors.length > 0 && (
              <div className="max-h-28 overflow-auto border-t border-red-500/20 bg-red-500/5 px-3 py-1.5 text-xs text-red-600">
                {previewErrors.map((message, i) => (
                  <p key={i} className="truncate" title={message}>
                    {message}
                  </p>
                ))}
                <p className="mt-1 text-muted-foreground">The Apps agent sees these errors: ask it to fix them.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
