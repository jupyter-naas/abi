'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import {
  Check,
  GitMerge,
  GitPullRequest,
  Loader2,
  Plus,
  RefreshCw,
  Send,
  X,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { useEnsureSelectedRepo } from '@/stores/code';
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

interface Branch {
  name: string;
  protected: boolean;
}

interface DiffFile {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  patch?: string | null;
  old_path?: string | null;
}

function DiffViewer({ files }: { files: DiffFile[] }) {
  if (files.length === 0) {
    return <p className="text-xs text-muted-foreground">No file changes.</p>;
  }
  return (
    <div className="space-y-3">
      {files.map((f) => (
        <div key={f.path} className="overflow-hidden rounded-md border border-border/60">
          <div className="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-3 py-1.5 text-xs">
            <span className="rounded border border-border px-1 py-0.5 text-[10px] uppercase text-muted-foreground">
              {f.status}
            </span>
            <span className="truncate font-mono">
              {f.old_path && f.old_path !== f.path ? `${f.old_path} → ${f.path}` : f.path}
            </span>
            <span className="ml-auto flex-shrink-0 font-mono">
              <span className="text-emerald-600">+{f.additions}</span>{' '}
              <span className="text-red-600">−{f.deletions}</span>
            </span>
          </div>
          {f.patch ? (
            <div className="overflow-x-auto font-mono text-[12px] leading-[1.45]">
              {f.patch.split('\n').map((line, i) => {
                const tone = line.startsWith('+')
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                  : line.startsWith('-')
                    ? 'bg-red-500/10 text-red-700 dark:text-red-400'
                    : line.startsWith('@@')
                      ? 'bg-workspace-accent-5 text-muted-foreground'
                      : 'text-foreground';
                return (
                  <div key={i} className={cn('whitespace-pre px-3', tone)}>
                    {line || ' '}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              Binary file or no inline diff available.
            </p>
          )}
        </div>
      ))}
    </div>
  );
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

export default function PullRequestsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const wsQuery = `workspace_id=${encodeURIComponent(workspaceId)}`;
  const selectedRepoId = useEnsureSelectedRepo(workspaceId);
  const repoId = selectedRepoId;

  const [branches, setBranches] = useState<Branch[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selected, setSelected] = useState<Proposal | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [diff, setDiff] = useState<DiffFile[]>([]);
  const [reviewEvent, setReviewEvent] = useState<'approved' | 'changes_requested'>('approved');
  const [reviewBody, setReviewBody] = useState('');
  const [newComment, setNewComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New-PR form
  const [showCreate, setShowCreate] = useState(false);
  const [prSource, setPrSource] = useState('');
  const [prTarget, setPrTarget] = useState('main');
  const [prTitle, setPrTitle] = useState('');
  const [prBody, setPrBody] = useState('');

  const pendingNumber = useRef<number | null>(null);

  const repoQuery = (repo: string) => `${wsQuery}&repo_id=${encodeURIComponent(repo)}`;

  const fetchProposals = useCallback(
    async (repo: string) => {
      if (!repo) return;
      try {
        const data = await readJson<Proposal[]>(
          await authFetch(`/api/code-review/proposals?${repoQuery(repo)}&state=all`),
        );
        setProposals(data);
        if (pendingNumber.current != null) {
          const match = data.find((p) => p.number === pendingNumber.current);
          pendingNumber.current = null;
          if (match) void select(match, repo);
        }
      } catch (e) {
        setError((e as Error).message);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wsQuery],
  );

  const fetchComments = useCallback(
    async (repo: string, number: number) => {
      try {
        const data = await readJson<Comment[]>(
          await authFetch(`/api/code-review/proposal/comments?${repoQuery(repo)}&number=${number}`),
        );
        setComments(data);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wsQuery],
  );

  const fetchDiff = useCallback(
    async (repo: string, number: number) => {
      try {
        const data = await readJson<{ files: DiffFile[] }>(
          await authFetch(`/api/code-review/proposal/diff?${repoQuery(repo)}&number=${number}`),
        );
        setDiff(data.files ?? []);
      } catch {
        setDiff([]);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [wsQuery],
  );

  // Read deep-link params once: ?new=1&source=… (open create form), ?number=…
  // (select a PR after load).
  useEffect(() => {
    const numberParam = searchParams.get('number');
    if (numberParam) pendingNumber.current = Number(numberParam);
    if (searchParams.get('new') === '1') {
      setShowCreate(true);
      setPrSource(searchParams.get('source') ?? '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load branches + proposals for the selected repository (re-runs on change).
  useEffect(() => {
    if (!workspaceId || !selectedRepoId) return;
    void (async () => {
      try {
        const brs = await readJson<Branch[]>(
          await authFetch(
            `/api/coding-environments/branches?${wsQuery}&repo_id=${encodeURIComponent(selectedRepoId)}`,
          ),
        );
        setBranches(brs);
        await fetchProposals(selectedRepoId);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, selectedRepoId]);

  const select = useCallback(
    async (proposal: Proposal, repo = repoId) => {
      setSelected(proposal);
      setComments([]);
      setDiff([]);
      setReviewBody('');
      void fetchDiff(repo, proposal.number);
      await fetchComments(repo, proposal.number);
      const fresh = await readJson<Proposal>(
        await authFetch(`/api/code-review/proposal?${repoQuery(repo)}&number=${proposal.number}`),
      ).catch(() => null);
      if (fresh) setSelected(fresh);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [repoId, fetchComments, fetchDiff],
  );

  const reload = async () => {
    await fetchProposals(repoId);
    if (selected) {
      const fresh = await readJson<Proposal>(
        await authFetch(`/api/code-review/proposal?${repoQuery(repoId)}&number=${selected.number}`),
      ).catch(() => null);
      if (fresh) setSelected(fresh);
    }
  };

  const createPr = async () => {
    if (!prTitle.trim() || !prSource || !prTarget) return;
    setBusy(true);
    setError(null);
    try {
      const created = await readJson<Proposal>(
        await authFetch('/api/code-review/proposals', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            repo_id: repoId,
            title: prTitle.trim(),
            body: prBody.trim(),
            source_branch: prSource,
            target_branch: prTarget,
          }),
        }),
      );
      setShowCreate(false);
      setPrTitle('');
      setPrBody('');
      await fetchProposals(repoId);
      void select(created);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submitReview = async () => {
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
          event: reviewEvent,
          body: reviewBody.trim() || undefined,
        }),
      });
      setReviewBody('');
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
      <div className="flex flex-shrink-0 items-center gap-2 border-b border-border/50 px-4 py-2">
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-2.5 py-1 text-xs font-medium text-white hover:opacity-90"
          >
            <Plus size={14} />
            New PR
          </button>
          <button
            onClick={() => void reload()}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-workspace-accent-10"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="space-y-3 border-b border-border/50 bg-workspace-accent-5 px-4 py-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">New pull request</h2>
            <button onClick={() => setShowCreate(false)} aria-label="Close">
              <X size={16} className="text-muted-foreground" />
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select
              value={prSource}
              onChange={(e) => setPrSource(e.target.value)}
              className="rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
            >
              <option value="">source branch…</option>
              {branches.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
            <span className="text-muted-foreground">→</span>
            <select
              value={prTarget}
              onChange={(e) => setPrTarget(e.target.value)}
              className="rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
            >
              {branches.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <input
            value={prTitle}
            onChange={(e) => setPrTitle(e.target.value)}
            placeholder="Title"
            className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
          />
          <textarea
            value={prBody}
            onChange={(e) => setPrBody(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
          />
          <button
            onClick={createPr}
            disabled={busy || !prTitle.trim() || !prSource || prSource === prTarget}
            className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <GitPullRequest size={14} />}
            Create pull request
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="w-72 flex-shrink-0 overflow-y-auto border-r border-border/50">
          {proposals.length === 0 ? (
            <p className="p-4 text-xs text-muted-foreground">No pull requests yet.</p>
          ) : (
            proposals.map((p) => (
              <button
                key={p.id}
                onClick={() => void select(p)}
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
              Select a pull request, or create one.
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

              <div className="space-y-2">
                <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Files changed{diff.length > 0 ? ` (${diff.length})` : ''}
                </h3>
                <DiffViewer files={diff} />
              </div>

              {selected.state === 'open' && (
                <div className="space-y-2 rounded-md border border-border/60 p-3">
                  <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Review
                  </h3>
                  <div className="flex items-center gap-4 text-sm">
                    {(['approved', 'changes_requested'] as const).map((ev) => (
                      <label key={ev} className="flex items-center gap-1.5">
                        <input
                          type="radio"
                          name="review-event"
                          checked={reviewEvent === ev}
                          onChange={() => setReviewEvent(ev)}
                        />
                        {ev === 'approved' ? 'Approve' : 'Request changes'}
                      </label>
                    ))}
                  </div>
                  <textarea
                    value={reviewBody}
                    onChange={(e) => setReviewBody(e.target.value)}
                    placeholder="Leave a review comment (optional)"
                    rows={2}
                    className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                  />
                  <div className="flex items-center gap-2">
                    <button
                      onClick={submitReview}
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-workspace-accent-10 disabled:opacity-50"
                    >
                      {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                      Submit review
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
