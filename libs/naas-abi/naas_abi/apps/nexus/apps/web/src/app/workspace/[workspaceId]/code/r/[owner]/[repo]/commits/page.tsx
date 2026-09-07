'use client';

import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Copy, GitBranch, GitCommit, Loader2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';

interface Branch {
  name: string;
  protected: boolean;
}
interface Commit {
  sha: string;
  message: string;
  author: string;
  date: string | null;
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function RepoCommitsPage() {
  const params = useParams();
  const search = useSearchParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const repoId = `${owner}/${repo}`;
  const q = `workspace_id=${encodeURIComponent(workspaceId)}&repo_id=${encodeURIComponent(repoId)}`;

  const [branches, setBranches] = useState<Branch[]>([]);
  const [ref, setRef] = useState(search.get('ref') || '');
  const [commits, setCommits] = useState<Commit[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Branch list + default ref.
  useEffect(() => {
    if (!workspaceId || !repoId) return;
    void (async () => {
      try {
        const [bRes, rRes] = await Promise.all([
          authFetch(`/api/coding-environments/branches?${q}`),
          authFetch(`/api/coding-environments/repos?workspace_id=${encodeURIComponent(workspaceId)}`),
        ]);
        const bs = bRes.ok ? ((await bRes.json()) as Branch[]) : [];
        setBranches(bs);
        if (!ref) {
          const repos = rRes.ok
            ? ((await rRes.json()) as Array<{ repo_id: string; default_branch: string }>)
            : [];
          const m = repos.find((r) => r.repo_id === repoId);
          setRef(m?.default_branch || bs[0]?.name || 'main');
        }
      } catch (e) {
        setError((e as Error).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, repoId]);

  useEffect(() => {
    if (!ref) return;
    setLoading(true);
    void (async () => {
      try {
        const res = await authFetch(
          `/api/coding-environments/repo-commits?${q}&ref=${encodeURIComponent(ref)}&limit=50`,
        );
        setCommits(res.ok ? ((await res.json()) as Commit[]) : []);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref]);

  const copySha = async (sha: string) => {
    try {
      await navigator.clipboard.writeText(sha);
      setCopied(sha);
      window.setTimeout(() => setCopied(''), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border/50 px-4 py-2">
        <div className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs">
          <GitBranch size={13} className="text-muted-foreground" />
          <select
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            className="bg-transparent outline-none"
          >
            {branches.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <span className="text-xs text-muted-foreground">
          {commits.length} commit{commits.length === 1 ? '' : 's'}
        </span>
      </div>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl p-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Loading…
            </div>
          ) : commits.length === 0 ? (
            <p className="text-sm text-muted-foreground">No commits on this branch yet.</p>
          ) : (
            <ul className="overflow-hidden rounded-lg border border-border/60">
              {commits.map((c) => (
                <li
                  key={c.sha}
                  className="flex items-center gap-3 border-b border-border/30 px-3 py-2 last:border-0 hover:bg-workspace-accent-5"
                >
                  <GitCommit size={15} className="flex-shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{c.message}</p>
                    <p className="text-xs text-muted-foreground">
                      {c.author} · {timeAgo(c.date)}
                    </p>
                  </div>
                  <button
                    onClick={() => copySha(c.sha)}
                    title="Copy commit SHA"
                    className="flex flex-shrink-0 items-center gap-1 rounded border border-border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground hover:text-workspace-accent"
                  >
                    {copied === c.sha ? 'Copied' : c.sha.slice(0, 7)}
                    {copied !== c.sha && <Copy size={11} />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
