'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  CircleDot,
  ExternalLink,
  FileDiff,
  GitCommitVertical,
  GitMerge,
  Loader2,
  MessageSquare,
  Send,
  XCircle,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';
import {
  Avatar,
  BranchChip,
  Comment,
  CommitItem,
  DiffFile,
  DiffViewer,
  Markdown,
  Proposal,
  Review,
  StateBadge,
  btnOutline,
  btnPrimary,
  readJson,
  timeAgo,
} from '../_components/prkit';

interface Check {
  name: string;
  status: string;
  conclusion: string | null;
}

type Tab = 'conversation' | 'commits' | 'files';

const REVIEW_LABEL: Record<string, string> = {
  approved: 'approved these changes',
  changes_requested: 'requested changes',
  comment: 'commented',
};

export default function PrDetailPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const number = Number(params?.number);
  const repoId = `${owner}/${repo}`;
  const repoBase = `/workspace/${workspaceId}/code/r/${repoId}`;
  const q = `workspace_id=${encodeURIComponent(workspaceId)}&repo_id=${encodeURIComponent(repoId)}&number=${number}`;

  const [pr, setPr] = useState<Proposal | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [commits, setCommits] = useState<CommitItem[]>([]);
  const [diff, setDiff] = useState<DiffFile[]>([]);
  const [checks, setChecks] = useState<Check[]>([]);
  const [tab, setTab] = useState<Tab>('conversation');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newComment, setNewComment] = useState('');
  const [showReview, setShowReview] = useState(false);
  const [reviewEvent, setReviewEvent] = useState<'approved' | 'changes_requested' | 'comment'>(
    'approved',
  );
  const [reviewBody, setReviewBody] = useState('');
  const [mergeMethod, setMergeMethod] = useState<'merge' | 'squash' | 'rebase'>('merge');

  const fetchPr = useCallback(async () => {
    const fresh = await readJson<Proposal>(await authFetch(`/api/code-review/proposal?${q}`));
    setPr(fresh);
    return fresh;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const fetchConversation = useCallback(async () => {
    const [cs, rs] = await Promise.all([
      readJson<Comment[]>(await authFetch(`/api/code-review/proposal/comments?${q}`)).catch(
        () => [] as Comment[],
      ),
      readJson<Review[]>(await authFetch(`/api/code-review/proposal/reviews?${q}`)).catch(
        () => [] as Review[],
      ),
    ]);
    setComments(cs);
    setReviews(rs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  // Initial load.
  useEffect(() => {
    if (!workspaceId || !repoId || !Number.isFinite(number)) return;
    setLoading(true);
    void (async () => {
      try {
        await Promise.all([fetchPr(), fetchConversation()]);
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  // Lazy per-tab data.
  useEffect(() => {
    if (!pr) return;
    if (tab === 'files' && diff.length === 0) {
      void (async () => {
        try {
          const d = await readJson<{ files: DiffFile[] }>(
            await authFetch(`/api/code-review/proposal/diff?${q}`),
          );
          setDiff(d.files ?? []);
        } catch {
          setDiff([]);
        }
      })();
    }
    if (tab === 'commits' && commits.length === 0) {
      void (async () => {
        try {
          setCommits(
            await readJson<CommitItem[]>(
              await authFetch(`/api/code-review/proposal/commits?${q}`),
            ),
          );
        } catch {
          setCommits([]);
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, pr]);

  // Checks (for the merge box) once the PR is open.
  useEffect(() => {
    if (!pr || pr.state !== 'open') return;
    void (async () => {
      try {
        setChecks(
          await readJson<Check[]>(await authFetch(`/api/code-review/proposal/checks?${q}`)),
        );
      } catch {
        setChecks([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pr?.state]);

  const reloadAll = async () => {
    await Promise.all([fetchPr(), fetchConversation()]);
    setDiff([]);
    setCommits([]);
  };

  const addComment = async () => {
    if (!newComment.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await authFetch('/api/code-review/proposal/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number,
          body: newComment.trim(),
        }),
      }).then(readJson);
      setNewComment('');
      await fetchConversation();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submitReview = async () => {
    setBusy(true);
    setError(null);
    try {
      await authFetch('/api/code-review/proposal/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number,
          event: reviewEvent,
          body: reviewBody.trim(),
        }),
      }).then(readJson);
      setReviewBody('');
      setShowReview(false);
      await reloadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const merge = async () => {
    setBusy(true);
    setError(null);
    try {
      await authFetch('/api/code-review/proposal/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          repo_id: repoId,
          number,
          method: mergeMethod,
        }),
      }).then(readJson);
      await reloadAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // Merge description + reviews, oldest first, for the timeline.
  const timeline = useMemo(() => {
    const items: Array<
      | { kind: 'comment'; at: number; data: Comment }
      | { kind: 'review'; at: number; data: Review }
    > = [];
    for (const c of comments) items.push({ kind: 'comment', at: ts(c.created_at), data: c });
    for (const r of reviews) {
      // skip empty plain comments that carry no body (they add noise)
      if (r.state === 'comment' && !r.body.trim()) continue;
      items.push({ kind: 'review', at: ts(r.submitted_at), data: r });
    }
    return items.sort((a, b) => a.at - b.at);
  }, [comments, reviews]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={16} className="animate-spin" /> Loading pull request…
      </div>
    );
  }
  if (!pr) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <p>{error ?? 'Pull request not found.'}</p>
        <Link href={`${repoBase}/pulls`} className={btnOutline}>
          <ArrowLeft size={14} /> Back to pull requests
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border/50 px-5 py-3">
        <Link
          href={`${repoBase}/pulls`}
          className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={13} /> Pull requests
        </Link>
        <div className="flex items-start gap-2">
          <h1 className="text-lg font-semibold leading-tight">
            {pr.title} <span className="font-normal text-muted-foreground">#{pr.number}</span>
          </h1>
          {pr.html_url && (
            <a
              href={pr.html_url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 text-muted-foreground hover:text-foreground"
              title="Open in Forgejo"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <StateBadge state={pr.state} />
          <span className="flex items-center gap-1">
            <Avatar name={pr.author} size={16} />
            <span className="font-medium text-foreground">{pr.author}</span>
            wants to merge {commits.length > 0 ? `${commits.length} commit(s) ` : ''}into
          </span>
          <BranchChip name={pr.target_branch} />
          <span>from</span>
          <BranchChip name={pr.source_branch} />
        </div>
      </div>

      {/* Tab bar */}
      <nav className="flex flex-shrink-0 items-center gap-1 border-b border-border/50 px-5">
        {(
          [
            ['conversation', 'Conversation', timeline.length, MessageSquare],
            ['commits', 'Commits', commits.length || null, GitCommitVertical],
            ['files', 'Files changed', diff.length || null, FileDiff],
          ] as const
        ).map(([key, label, count, Icon]) => (
          <button
            key={key}
            onClick={() => setTab(key as Tab)}
            className={cn(
              '-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
              tab === key
                ? 'border-workspace-accent text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon size={15} />
            {label}
            {count ? <span className="text-xs text-muted-foreground">{count}</span> : null}
          </button>
        ))}
      </nav>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-5 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      {/* Tab content */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {tab === 'conversation' && (
          <div className="mx-auto max-w-3xl space-y-4">
            {/* Description */}
            <article className="overflow-hidden rounded-md border border-border/60">
              <div className="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                <Avatar name={pr.author} size={18} />
                <span className="font-medium text-foreground">{pr.author}</span>
                <span>opened this pull request</span>
              </div>
              <div className="px-3 py-3 text-sm">
                {pr.body.trim() ? (
                  <Markdown>{pr.body}</Markdown>
                ) : (
                  <span className="text-muted-foreground">No description provided.</span>
                )}
              </div>
            </article>

            {/* Timeline */}
            {timeline.map((item) =>
              item.kind === 'comment' ? (
                <CommentCard key={`c-${item.data.id}`} comment={item.data} />
              ) : (
                <ReviewEvent key={`r-${item.data.id}`} review={item.data} />
              ),
            )}

            {/* Merge box */}
            {pr.state === 'open' && (
              <MergeBox
                pr={pr}
                checks={checks}
                method={mergeMethod}
                setMethod={setMergeMethod}
                busy={busy}
                onMerge={merge}
              />
            )}
            {pr.state === 'merged' && (
              <div className="flex items-center gap-2 rounded-md border border-violet-500/30 bg-violet-500/10 px-3 py-2.5 text-sm text-violet-600">
                <GitMerge size={16} /> This pull request was merged.
              </div>
            )}

            {/* Comment composer */}
            <div className="rounded-md border border-border/60 p-3">
              <textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Leave a comment"
                rows={3}
                className="w-full resize-y rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
              />
              <div className="mt-2 flex justify-end">
                <button onClick={addComment} disabled={busy || !newComment.trim()} className={btnPrimary}>
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  Comment
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === 'commits' && (
          <div className="mx-auto max-w-3xl">
            {commits.length === 0 ? (
              <p className="text-sm text-muted-foreground">No commits.</p>
            ) : (
              <ul className="overflow-hidden rounded-md border border-border/60 divide-y divide-border/40">
                {commits.map((c) => (
                  <li key={c.sha} className="flex items-center gap-3 px-3 py-2.5">
                    <GitCommitVertical size={16} className="flex-shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{c.message}</p>
                      <p className="text-xs text-muted-foreground">
                        {c.author} · {timeAgo(c.date)}
                      </p>
                    </div>
                    <code className="flex-shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
                      {c.sha.slice(0, 7)}
                    </code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === 'files' && (
          <div className="mx-auto max-w-4xl space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-xs text-muted-foreground">
                {diff.length} file{diff.length === 1 ? '' : 's'} changed
              </p>
              {pr.state === 'open' && (
                <button
                  onClick={() => setShowReview((v) => !v)}
                  className={cn(btnPrimary, 'ml-auto px-2.5 py-1 text-xs')}
                >
                  <Check size={14} /> Review changes
                </button>
              )}
            </div>

            {showReview && pr.state === 'open' && (
              <div className="space-y-2 rounded-md border border-border/60 bg-workspace-accent-5 p-3">
                <div className="flex flex-wrap gap-3 text-sm">
                  {(
                    [
                      ['comment', 'Comment'],
                      ['approved', 'Approve'],
                      ['changes_requested', 'Request changes'],
                    ] as const
                  ).map(([ev, label]) => (
                    <label key={ev} className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        name="review-event"
                        checked={reviewEvent === ev}
                        onChange={() => setReviewEvent(ev)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
                <textarea
                  value={reviewBody}
                  onChange={(e) => setReviewBody(e.target.value)}
                  placeholder="Review summary (optional)"
                  rows={2}
                  className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
                />
                <div className="flex justify-end">
                  <button onClick={submitReview} disabled={busy} className={btnPrimary}>
                    {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    Submit review
                  </button>
                </div>
              </div>
            )}

            <DiffViewer files={diff} />
          </div>
        )}
      </div>
    </div>
  );
}

function ts(iso: string | null): number {
  if (!iso) return 0;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function CommentCard({ comment }: { comment: Comment }) {
  return (
    <article className="overflow-hidden rounded-md border border-border/60">
      <div className="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <Avatar name={comment.author} size={18} />
        <span className="font-medium text-foreground">{comment.author}</span>
        <span>commented {timeAgo(comment.created_at)}</span>
        {comment.path && (
          <code className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">
            {comment.path}
            {comment.line ? `:${comment.line}` : ''}
          </code>
        )}
      </div>
      <div className="px-3 py-3 text-sm">
        <Markdown>{comment.body}</Markdown>
      </div>
    </article>
  );
}

function ReviewEvent({ review }: { review: Review }) {
  const cfg =
    review.state === 'approved'
      ? { Icon: CheckCircle2, tone: 'text-emerald-600' }
      : review.state === 'changes_requested'
        ? { Icon: XCircle, tone: 'text-red-600' }
        : { Icon: CircleDot, tone: 'text-muted-foreground' };
  const { Icon, tone } = cfg;
  return (
    <div className="rounded-md border border-border/60">
      <div className="flex items-center gap-2 px-3 py-2 text-sm">
        <Icon size={16} className={tone} />
        <Avatar name={review.author} size={16} />
        <span className="font-medium">{review.author}</span>
        <span className="text-muted-foreground">
          {REVIEW_LABEL[review.state] ?? 'reviewed'} {timeAgo(review.submitted_at)}
        </span>
      </div>
      {review.body.trim() && (
        <div className="border-t border-border/40 px-3 py-2 text-sm">
          <Markdown>{review.body}</Markdown>
        </div>
      )}
    </div>
  );
}

function MergeBox({
  pr,
  checks,
  method,
  setMethod,
  busy,
  onMerge,
}: {
  pr: Proposal;
  checks: Check[];
  method: 'merge' | 'squash' | 'rebase';
  setMethod: (m: 'merge' | 'squash' | 'rebase') => void;
  busy: boolean;
  onMerge: () => void;
}) {
  const failing = checks.filter((c) => c.status === 'failure').length;
  const pending = checks.filter((c) => c.status === 'pending').length;
  const canMerge = pr.mergeable && failing === 0;
  return (
    <div className="overflow-hidden rounded-md border border-border/60">
      <div className="space-y-1.5 border-b border-border/50 bg-muted/20 px-3 py-2.5 text-sm">
        {checks.length > 0 && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {failing > 0 ? (
              <XCircle size={14} className="text-red-600" />
            ) : pending > 0 ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <CheckCircle2 size={14} className="text-emerald-600" />
            )}
            {checks.length} check{checks.length === 1 ? '' : 's'}
            {failing > 0 ? ` · ${failing} failing` : pending > 0 ? ` · ${pending} pending` : ' passed'}
          </p>
        )}
        <p className="flex items-center gap-1.5 font-medium">
          {canMerge ? (
            <>
              <CheckCircle2 size={16} className="text-emerald-600" />
              This branch has no conflicts
            </>
          ) : (
            <>
              <XCircle size={16} className="text-amber-600" />
              {pr.mergeable ? 'Checks are not passing' : 'Cannot be merged automatically'}
            </>
          )}
        </p>
        {pr.approvals > 0 && (
          <p className="flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle2 size={13} /> {pr.approvals} approval{pr.approvals === 1 ? '' : 's'}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as 'merge' | 'squash' | 'rebase')}
          className="rounded-md border border-border bg-transparent px-2 py-1.5 text-xs outline-none focus:border-workspace-accent"
        >
          <option value="merge">Create a merge commit</option>
          <option value="squash">Squash and merge</option>
          <option value="rebase">Rebase and merge</option>
        </select>
        <button onClick={onMerge} disabled={busy || !canMerge} className={btnPrimary}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <GitMerge size={14} />}
          Merge pull request
        </button>
      </div>
    </div>
  );
}
