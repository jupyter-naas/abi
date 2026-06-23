'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Check, GitMerge, GitPullRequest, Loader2, RefreshCw, Send } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';

interface Proposal {
  id: string;
  number: number;
  title: string;
  body: string;
  state: string;
  source_branch: string;
  target_branch: string;
  author: string;
  mergeable: boolean;
  approvals: number;
  html_url: string;
}

interface Comment {
  id: string;
  path: string | null;
  line: number | null;
  body: string;
  author: string;
  created_at: string | null;
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function StatePill({ state }: { state: string }) {
  const tone =
    state === 'merged'
      ? 'bg-violet-500/15 text-violet-600'
      : state === 'closed'
        ? 'bg-muted text-muted-foreground'
        : 'bg-emerald-500/15 text-emerald-600';
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', tone)}>
      {state}
    </span>
  );
}

export default function ReviewPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const repoKey = `nexus:review:repo:${workspaceId}`;
  const wsQuery = `workspace_id=${encodeURIComponent(workspaceId)}`;

  const [repoId, setRepoId] = useState('');
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<Proposal | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProposals = useCallback(
    async (repo: string) => {
      if (!repo) return;
      setError(null);
      try {
        const data = await readJson<Proposal[]>(
          await authFetch(
            `/api/code-review/proposals?${wsQuery}&repo_id=${encodeURIComponent(repo)}&state=all`,
          ),
        );
        setProposals(data);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [wsQuery],
  );

  const fetchComments = useCallback(
    async (repo: string, number: number) => {
      try {
        const data = await readJson<Comment[]>(
          await authFetch(
            `/api/code-review/proposal/comments?${wsQuery}&repo_id=${encodeURIComponent(repo)}&number=${number}`,
          ),
        );
        setComments(data);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [wsQuery],
  );

  useEffect(() => {
    if (!workspaceId) return;
    const saved = window.localStorage.getItem(repoKey);
    if (saved) {
      setRepoId(saved);
      void fetchProposals(saved);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  const select = async (proposal: Proposal) => {
    setSelected(proposal);
    setComments([]);
    await fetchComments(repoId, proposal.number);
    // Fetch authoritative detail — approval counts are only populated there.
    const fresh = await readJson<Proposal>(
      await authFetch(
        `/api/code-review/proposal?${wsQuery}&repo_id=${encodeURIComponent(repoId)}&number=${proposal.number}`,
      ),
    ).catch(() => null);
    if (fresh) setSelected(fresh);
  };

  const reload = async () => {
    await fetchProposals(repoId);
    if (selected) {
      const fresh = await readJson<Proposal>(
        await authFetch(
          `/api/code-review/proposal?${wsQuery}&repo_id=${encodeURIComponent(repoId)}&number=${selected.number}`,
        ),
      ).catch(() => null);
      if (fresh) setSelected(fresh);
    }
  };

  const approve = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await authFetch('/api/code-review/proposal/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number: selected.number,
          event: 'approved',
        }),
      });
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const merge = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch('/api/code-review/proposal/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number: selected.number,
        }),
      });
      await readJson(res);
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const comment = async () => {
    if (!selected || !newComment.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await authFetch('/api/code-review/proposal/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number: selected.number,
          body: newComment.trim(),
        }),
      });
      setNewComment('');
      await fetchComments(repoId, selected.number);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <GitPullRequest size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Code review</h1>
        <div className="ml-auto flex items-center gap-2">
          <input
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="owner/repo"
            className="w-44 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs outline-none focus:border-workspace-accent"
          />
          <button
            onClick={() => {
              window.localStorage.setItem(repoKey, repoId);
              void fetchProposals(repoId);
            }}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
          >
            <RefreshCw size={14} />
            Load
          </button>
        </div>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 flex-shrink-0 overflow-y-auto border-r border-border/50">
          {proposals.length === 0 ? (
            <p className="p-4 text-xs text-muted-foreground">
              No proposals. Enter a repo (owner/repo) and click Load.
            </p>
          ) : (
            proposals.map((p) => (
              <button
                key={p.id}
                onClick={() => select(p)}
                className={cn(
                  'flex w-full flex-col gap-1 border-b border-border/30 px-3 py-2.5 text-left transition-colors hover:bg-workspace-accent-5',
                  selected?.number === p.number && 'bg-workspace-accent-10',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">#{p.number}</span>
                  <StatePill state={p.state} />
                </div>
                <span className="truncate text-sm font-medium">{p.title}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {p.source_branch} → {p.target_branch}
                </span>
              </button>
            ))
          )}
        </aside>

        <main className="flex-1 overflow-y-auto">
          {!selected ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a proposal to review.
            </div>
          ) : (
            <div className="space-y-4 p-5">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-medium">{selected.title}</h2>
                  <StatePill state={selected.state} />
                </div>
                <p className="text-xs text-muted-foreground">
                  #{selected.number} · {selected.source_branch} → {selected.target_branch} ·{' '}
                  {selected.approvals} approval(s)
                </p>
              </div>

              {selected.body && (
                <p className="whitespace-pre-wrap rounded-md border border-border/50 p-3 text-sm">
                  {selected.body}
                </p>
              )}

              {selected.state === 'open' && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={approve}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-md border border-emerald-500/40 px-3 py-1.5 text-xs font-medium text-emerald-600 hover:bg-emerald-500/10 disabled:opacity-50"
                  >
                    <Check size={14} />
                    Approve
                  </button>
                  <button
                    onClick={merge}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                  >
                    {busy ? <Loader2 size={14} className="animate-spin" /> : <GitMerge size={14} />}
                    Merge
                  </button>
                </div>
              )}

              <div className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Comments
                </h3>
                {comments.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No comments yet.</p>
                ) : (
                  comments.map((c) => (
                    <div key={c.id} className="rounded-md border border-border/50 p-2.5 text-sm">
                      <p className="mb-0.5 text-xs text-muted-foreground">
                        {c.author}
                        {c.path ? ` · ${c.path}${c.line ? `:${c.line}` : ''}` : ''}
                      </p>
                      <p className="whitespace-pre-wrap">{c.body}</p>
                    </div>
                  ))
                )}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Add a comment"
                    className="flex-1 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                  />
                  <button
                    onClick={comment}
                    disabled={busy || !newComment.trim()}
                    className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-workspace-accent-10 disabled:opacity-50"
                  >
                    <Send size={14} />
                    Send
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
