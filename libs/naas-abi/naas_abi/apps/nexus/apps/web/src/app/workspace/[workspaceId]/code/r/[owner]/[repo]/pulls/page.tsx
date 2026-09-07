'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  CheckCircle2,
  GitMerge,
  GitPullRequest,
  GitPullRequestClosed,
  Loader2,
  Plus,
  RefreshCw,
  X,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';
import {
  Avatar,
  Branch,
  BranchChip,
  Proposal,
  btnOutline,
  btnPrimary,
  readJson,
} from './_components/prkit';

type Filter = 'open' | 'closed' | 'all';

function rowIcon(state: string) {
  if (state === 'merged') return <GitMerge size={16} className="text-violet-600" />;
  if (state === 'closed') return <GitPullRequestClosed size={16} className="text-red-600" />;
  return <GitPullRequest size={16} className="text-emerald-600" />;
}

export default function RepoPullsPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const repoId = `${owner}/${repo}`;
  const repoBase = `/workspace/${workspaceId}/code/r/${repoId}`;
  const q = `workspace_id=${encodeURIComponent(workspaceId)}&repo_id=${encodeURIComponent(repoId)}`;

  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [filter, setFilter] = useState<Filter>('open');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create-PR form
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [prSource, setPrSource] = useState('');
  const [prTarget, setPrTarget] = useState('main');
  const [prTitle, setPrTitle] = useState('');
  const [prBody, setPrBody] = useState('');

  const refresh = useCallback(async () => {
    if (!workspaceId || !repoId) return;
    setLoading(true);
    try {
      const data = await readJson<Proposal[]>(
        await authFetch(`/api/code-review/proposals?${q}&state=all`),
      );
      setProposals(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Branch list (for the create form) + deep-link ?new=1&source=…
  useEffect(() => {
    if (!workspaceId || !repoId) return;
    void (async () => {
      try {
        const bs = await readJson<Branch[]>(
          await authFetch(`/api/coding-environments/branches?${q}`),
        );
        setBranches(bs);
      } catch {
        // create form just shows no options
      }
    })();
    if (search.get('new') === '1') {
      setShowCreate(true);
      setPrSource(search.get('source') ?? '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const openCount = proposals.filter((p) => p.state === 'open').length;
  const closedCount = proposals.filter((p) => p.state !== 'open').length;
  const shown = proposals.filter((p) =>
    filter === 'all' ? true : filter === 'open' ? p.state === 'open' : p.state !== 'open',
  );

  const createPr = async () => {
    if (!prTitle.trim() || !prSource || prSource === prTarget) return;
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
      router.push(`${repoBase}/pulls/${created.number}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Filter tabs + actions */}
      <div className="flex flex-shrink-0 items-center gap-1 border-b border-border/50 px-4 py-2">
        {(
          [
            ['open', 'Open', openCount, <GitPullRequest key="o" size={14} />],
            ['closed', 'Closed', closedCount, <GitPullRequestClosed key="c" size={14} />],
            ['all', 'All', proposals.length, null],
          ] as const
        ).map(([key, label, count, icon]) => (
          <button
            key={key}
            onClick={() => setFilter(key as Filter)}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium transition-colors',
              filter === key
                ? 'bg-workspace-accent-10 text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {icon}
            {label}
            <span className="text-xs text-muted-foreground">{count}</span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => void refresh()} className={cn(btnOutline, 'px-2.5 py-1 text-xs')}>
            <RefreshCw size={14} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className={cn(btnPrimary, 'px-2.5 py-1 text-xs')}
          >
            <Plus size={14} />
            New pull request
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
            placeholder="Describe your changes (optional)"
            rows={3}
            className="w-full rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
          />
          <button
            onClick={createPr}
            disabled={busy || !prTitle.trim() || !prSource || prSource === prTarget}
            className={btnPrimary}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <GitPullRequest size={14} />}
            Create pull request
          </button>
        </div>
      )}

      {/* List */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : shown.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-12 text-center text-sm text-muted-foreground">
            <GitPullRequest size={28} className="opacity-40" />
            <p>No {filter === 'all' ? '' : filter} pull requests.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {shown.map((p) => (
              <li
                key={p.id}
                className="flex items-start gap-3 px-4 py-3 hover:bg-workspace-accent-5"
              >
                <span className="mt-0.5">{rowIcon(p.state)}</span>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`${repoBase}/pulls/${p.number}`}
                    className="text-sm font-semibold hover:text-workspace-accent hover:underline"
                  >
                    {p.title}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                    <span>#{p.number}</span>
                    <span className="flex items-center gap-1">
                      <Avatar name={p.author} size={14} /> {p.author}
                    </span>
                    <span className="flex items-center gap-1">
                      <BranchChip name={p.source_branch} /> →{' '}
                      <BranchChip name={p.target_branch} />
                    </span>
                  </div>
                </div>
                {p.approvals > 0 && (
                  <span className="flex flex-shrink-0 items-center gap-0.5 text-xs text-emerald-600">
                    <CheckCircle2 size={13} />
                    {p.approvals}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
