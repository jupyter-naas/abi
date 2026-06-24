'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Code,
  GitBranch,
  GitPullRequest,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useEnsureSelectedRepo } from '@/stores/code';

interface Branch {
  name: string;
  protected: boolean;
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // keep generic
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export default function BranchesPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const wsQuery = `workspace_id=${encodeURIComponent(workspaceId)}`;
  const codeBase = `/workspace/${workspaceId}/code`;
  const selectedRepoId = useEnsureSelectedRepo(workspaceId);
  const repoParam = selectedRepoId ? `&repo_id=${encodeURIComponent(selectedRepoId)}` : '';

  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState('main');
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await readJson<Branch[]>(
        await authFetch(`/api/coding-environments/branches?${wsQuery}${repoParam}`),
      );
      setBranches(data);
      setSource((prev) => (data.some((b) => b.name === prev) ? prev : (data[0]?.name ?? 'main')));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [wsQuery, repoParam]);

  useEffect(() => {
    if (!workspaceId) return;
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, selectedRepoId]);

  const create = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await readJson<Branch>(
        await authFetch('/api/coding-environments/branches', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            name: newName.trim(),
            source_branch: source,
            repo_id: selectedRepoId || null,
          }),
        }),
      );
      setNewName('');
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (name: string) => {
    if (!window.confirm(`Delete branch "${name}"? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch(
        `/api/coding-environments/branches?${wsQuery}${repoParam}&name=${encodeURIComponent(name)}`,
        { method: 'DELETE' },
      );
      await readJson(res);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <GitBranch size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Branches</h1>
        <button
          onClick={() => void refresh()}
          className="ml-auto flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          <section className="space-y-3 rounded-lg border border-border/60 p-4">
            <h2 className="text-sm font-medium">New branch</h2>
            <div className="flex flex-wrap items-end gap-2">
              <label className="space-y-1">
                <span className="block text-xs font-medium text-muted-foreground">From</span>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                >
                  {branches.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex-1 space-y-1">
                <span className="block text-xs font-medium text-muted-foreground">Name</span>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="feature/my-change"
                  className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                />
              </label>
              <button
                onClick={create}
                disabled={busy || !newName.trim()}
                className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Create
              </button>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium">All branches</h2>
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                Loading…
              </div>
            ) : branches.length === 0 ? (
              <p className="text-xs text-muted-foreground">No branches.</p>
            ) : (
              <ul className="space-y-2">
                {branches.map((b) => {
                  const deletable = !b.protected && b.name !== 'main';
                  return (
                    <li
                      key={b.name}
                      className="flex items-center gap-3 rounded-lg border border-border/60 p-3"
                    >
                      <GitBranch size={16} className="flex-shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium">{b.name}</span>
                      {b.protected && (
                        <span className="flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600">
                          <Lock size={11} />
                          protected
                        </span>
                      )}
                      <Link
                        href={`${codeBase}/workspaces?source=${encodeURIComponent(b.name)}`}
                        className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                      >
                        <Code size={13} />
                        New workspace
                      </Link>
                      <Link
                        href={`${codeBase}/pulls?new=1&source=${encodeURIComponent(b.name)}`}
                        className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                      >
                        <GitPullRequest size={13} />
                        New PR
                      </Link>
                      <button
                        onClick={() => remove(b.name)}
                        disabled={busy || !deletable}
                        title={deletable ? `Delete ${b.name}` : 'Protected / default branch'}
                        className="flex items-center rounded-md border border-border px-2 py-1.5 text-xs font-medium text-red-600 hover:bg-red-500/10 disabled:opacity-30"
                        aria-label={`Delete ${b.name}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
