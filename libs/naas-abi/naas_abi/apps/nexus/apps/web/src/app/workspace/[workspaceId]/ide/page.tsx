'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Code, ExternalLink, Loader2, Play, Plus, RefreshCw, Square, Trash2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';

interface Environment {
  id: string;
  name: string;
  phase: string;
  agent_ready: boolean;
}

interface Template {
  id: string;
  name: string;
  active_version_id: string;
}

interface AccessInfo {
  url: string;
  expires_at: string | null;
}

const POLL_INTERVAL_MS = 2500;

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new HttpError(res.status, detail);
  }
  return (await res.json()) as T;
}

function PhasePill({ phase, ready }: { phase: string; ready: boolean }) {
  const label = phase === 'running' && !ready ? 'starting' : phase;
  const tone =
    phase === 'running' && ready
      ? 'bg-emerald-500/15 text-emerald-600'
      : phase === 'error'
        ? 'bg-red-500/15 text-red-600'
        : phase === 'stopped'
          ? 'bg-muted text-muted-foreground'
          : 'bg-amber-500/15 text-amber-600';
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', tone)}>
      {label}
    </span>
  );
}

export default function IdePage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const storageKey = `nexus:ide:env:${workspaceId}`;
  const wsQuery = `workspace_id=${encodeURIComponent(workspaceId)}`;

  const [templates, setTemplates] = useState<Template[]>([]);
  const [env, setEnv] = useState<Environment | null>(null);
  const [accessUrl, setAccessUrl] = useState<string | null>(null);
  const [name, setName] = useState('dev');
  const [templateId, setTemplateId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchAccess = useCallback(
    async (envId: string) => {
      try {
        const data = await readJson<AccessInfo>(
          await authFetch(`/api/coding-environments/${envId}/access?${wsQuery}`),
        );
        setAccessUrl(data.url);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [wsQuery],
  );

  const refreshStatus = useCallback(
    async (envId: string): Promise<void> => {
      try {
        const data = await readJson<Environment>(
          await authFetch(`/api/coding-environments/${envId}?${wsQuery}`),
        );
        setEnv(data);
        if (data.phase === 'running' && data.agent_ready) {
          await fetchAccess(envId);
        }
      } catch (e) {
        setError((e as Error).message);
        // Forget the saved id if the backend says it's invalid or gone — 404
        // (deleted) or 400 (e.g. a stale id from a previously-configured
        // backend). Keep it on transient/server errors so a running workspace
        // isn't discarded.
        if (e instanceof HttpError && (e.status === 404 || e.status === 400)) {
          window.localStorage.removeItem(storageKey);
          setEnv(null);
        }
      }
    },
    [wsQuery, fetchAccess, storageKey],
  );

  const fetchTemplates = useCallback(async () => {
    try {
      const data = await readJson<Template[]>(
        await authFetch(`/api/coding-environments/templates?${wsQuery}`),
      );
      setTemplates(data);
      setTemplateId((prev) => prev || (data[0]?.id ?? ''));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [wsQuery]);

  // Initial load: templates + restore any previously created environment.
  useEffect(() => {
    if (!workspaceId) return;
    void fetchTemplates();
    const saved = window.localStorage.getItem(storageKey);
    if (saved) void refreshStatus(saved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  // Poll until the workspace is usable (running + agent ready) or rests in a
  // terminal state — not just while phase === 'provisioning' (Coder reports
  // 'running' before the agent connects).
  useEffect(() => {
    if (!env) return;
    const usable = env.phase === 'running' && env.agent_ready;
    const terminal = env.phase === 'stopped' || env.phase === 'error';
    if (usable || terminal) return;
    pollRef.current = setTimeout(() => {
      void refreshStatus(env.id);
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [env, refreshStatus]);

  const provision = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await readJson<Environment>(
        await authFetch('/api/coding-environments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workspace_id: workspaceId, name, template_id: templateId }),
        }),
      );
      setEnv(data);
      window.localStorage.setItem(storageKey, data.id);
      if (data.phase === 'running' && data.agent_ready) await fetchAccess(data.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const lifecycle = async (action: 'start' | 'stop') => {
    if (!env) return;
    setBusy(true);
    setError(null);
    setAccessUrl(null);
    try {
      const data = await readJson<Environment>(
        await authFetch(`/api/coding-environments/${env.id}/${action}?${wsQuery}`, {
          method: 'POST',
        }),
      );
      setEnv(data);
      if (data.phase === 'running' && data.agent_ready) await fetchAccess(data.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!env) return;
    setBusy(true);
    setError(null);
    try {
      await authFetch(`/api/coding-environments/${env.id}?${wsQuery}`, { method: 'DELETE' });
      window.localStorage.removeItem(storageKey);
      setEnv(null);
      setAccessUrl(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <Code size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Coding workspace</h1>
        {env && <PhasePill phase={env.phase} ready={env.agent_ready} />}
        <div className="ml-auto flex items-center gap-2">
          {env && (
            <>
              <button
                onClick={() => lifecycle(env.phase === 'stopped' ? 'start' : 'stop')}
                disabled={busy}
                className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10 disabled:opacity-50"
              >
                {env.phase === 'stopped' ? <Play size={14} /> : <Square size={14} />}
                {env.phase === 'stopped' ? 'Resume' : 'Pause'}
              </button>
              <button
                onClick={() => void refreshStatus(env.id)}
                disabled={busy}
                className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10 disabled:opacity-50"
              >
                <RefreshCw size={14} />
                Refresh
              </button>
              {accessUrl && (
                <a
                  href={accessUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                >
                  <ExternalLink size={14} />
                  Open
                </a>
              )}
              <button
                onClick={remove}
                disabled={busy}
                className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-500/10 disabled:opacity-50"
              >
                <Trash2 size={14} />
                Delete
              </button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="relative flex-1 overflow-hidden">
        {!env ? (
          <div className="flex h-full items-center justify-center p-6">
            <div className="w-full max-w-sm space-y-4 rounded-lg border border-border/60 p-6">
              <div className="flex items-center gap-2">
                <Code size={18} className="text-workspace-accent" />
                <h2 className="text-sm font-medium">New coding workspace</h2>
              </div>
              <p className="text-xs text-muted-foreground">
                Spin up an isolated browser IDE on a branch of the monorepo. You can pause and
                resume it later.
              </p>
              <label className="block space-y-1">
                <span className="text-xs font-medium text-muted-foreground">Name</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="dev"
                  className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-medium text-muted-foreground">Template</span>
                <select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                >
                  {templates.length === 0 && <option value="">No templates available</option>}
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name || t.id}
                    </option>
                  ))}
                </select>
              </label>
              <button
                onClick={provision}
                disabled={busy || !name || !templateId}
                className="flex w-full items-center justify-center gap-2 rounded-md bg-workspace-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                Create workspace
              </button>
            </div>
          </div>
        ) : accessUrl && env.phase === 'running' && env.agent_ready ? (
          <iframe
            title="Coding workspace editor"
            src={accessUrl}
            className="h-full w-full border-0"
            allow="clipboard-read; clipboard-write"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
            {env.phase === 'error' ? (
              <p className="text-sm">The workspace failed to start. Try deleting and recreating it.</p>
            ) : env.phase === 'stopped' ? (
              <p className="text-sm">Workspace paused. Resume it to start editing.</p>
            ) : (
              <>
                <Loader2 size={24} className="animate-spin" />
                <p className="text-sm">Preparing your workspace…</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
