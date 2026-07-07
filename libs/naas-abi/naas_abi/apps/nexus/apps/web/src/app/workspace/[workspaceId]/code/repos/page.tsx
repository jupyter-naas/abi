'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { BookMarked, GitBranch, Loader2, Lock, Plus, Search, Unlock } from 'lucide-react';
import { authFetch } from '@/stores/auth';

interface Repo {
  repo_id: string;
  name: string;
  default_branch: string;
  description: string;
  private: boolean;
  empty: boolean;
  updated_at: string | null;
}

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function ReposIndexPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const wsQuery = `workspace_id=${encodeURIComponent(workspaceId)}`;
  const codeBase = `/workspace/${workspaceId}/code`;

  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`/api/coding-environments/repos?${wsQuery}`);
      if (!res.ok) throw new Error(`Failed to load repositories (${res.status})`);
      setRepos((await res.json()) as Repo[]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [wsQuery]);

  useEffect(() => {
    if (workspaceId) void refresh();
  }, [workspaceId, refresh]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? repos.filter((r) => r.repo_id.toLowerCase().includes(q)) : repos;
  }, [repos, query]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <BookMarked size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Repositories</h1>
        <Link
          href={`${codeBase}/new`}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-workspace-accent px-2.5 py-1.5 text-xs font-medium text-white hover:opacity-90"
        >
          <Plus size={14} />
          New
        </Link>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a repository…"
              className="w-full rounded-md border border-border bg-transparent py-2 pl-9 pr-3 text-sm outline-none focus:border-workspace-accent"
            />
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Loading…
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No repositories.{' '}
              <Link href={`${codeBase}/new`} className="text-workspace-accent hover:underline">
                Create one
              </Link>
              .
            </p>
          ) : (
            <ul className="divide-y divide-border/50 rounded-lg border border-border/60">
              {filtered.map((r) => (
                <li key={r.repo_id} className="flex items-center gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`${codeBase}/r/${r.repo_id}`}
                        className="truncate text-sm font-semibold text-workspace-accent hover:underline"
                      >
                        {r.repo_id}
                      </Link>
                      <span className="flex items-center gap-1 rounded-full border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {r.private ? <Lock size={9} /> : <Unlock size={9} />}
                        {r.private ? 'Private' : 'Public'}
                      </span>
                      {r.empty && (
                        <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">
                          empty
                        </span>
                      )}
                    </div>
                    {r.description && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {r.description}
                      </p>
                    )}
                    <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
                      {r.default_branch && (
                        <span className="flex items-center gap-1">
                          <GitBranch size={11} />
                          {r.default_branch}
                        </span>
                      )}
                      {r.updated_at && <span>Updated {timeAgo(r.updated_at)}</span>}
                    </div>
                  </div>
                  <Link
                    href={`${codeBase}/r/${r.repo_id}`}
                    className="flex-shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                  >
                    Open
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
