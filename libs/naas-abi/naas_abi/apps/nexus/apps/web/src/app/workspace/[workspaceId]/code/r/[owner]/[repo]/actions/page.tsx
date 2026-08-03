'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  CheckCircle2,
  Clock,
  CircleSlash,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';
import { BranchChip, btnOutline, readJson, timeAgo } from '../pulls/_components/prkit';

interface WorkflowRun {
  id: number;
  name: string;
  workflow_id: string;
  display_title: string;
  run_number: number;
  event: string;
  status: string;
  head_branch: string;
  head_sha: string;
  url: string;
  created_at: string | null;
  run_started_at: string | null;
  updated_at: string | null;
}

const RUNNING = new Set(['running', 'in_progress', 'waiting', 'queued', 'blocked']);

function statusUI(status: string): { Icon: typeof CheckCircle2; cls: string; spin?: boolean } {
  switch (status) {
    case 'success':
      return { Icon: CheckCircle2, cls: 'text-emerald-600' };
    case 'failure':
    case 'error':
      return { Icon: XCircle, cls: 'text-red-600' };
    case 'cancelled':
    case 'skipped':
      return { Icon: CircleSlash, cls: 'text-muted-foreground' };
    case 'running':
    case 'in_progress':
      return { Icon: Loader2, cls: 'text-amber-500', spin: true };
    default:
      return { Icon: Clock, cls: 'text-amber-500' }; // waiting / queued / unknown
  }
}

function duration(start: string | null, end: string | null, live: boolean): string {
  if (!start) return '';
  const s = new Date(start).getTime();
  const e = live || !end ? Date.now() : new Date(end).getTime();
  if (Number.isNaN(s) || Number.isNaN(e) || e < s) return '';
  const sec = Math.round((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

export default function RepoActionsPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const repoId = `${owner}/${repo}`;
  const q = `workspace_id=${encodeURIComponent(workspaceId)}&repo_id=${encodeURIComponent(repoId)}`;

  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    if (!workspaceId || !repoId) return;
    try {
      const data = await readJson<WorkflowRun[]>(
        await authFetch(`/api/code-review/actions/runs?${q}`),
      );
      setRuns(data);
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

  // Auto-refresh while any run is in flight.
  useEffect(() => {
    if (!runs.some((r) => RUNNING.has(r.status))) return;
    pollRef.current = setTimeout(() => void refresh(), 5000);
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [runs, refresh]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-shrink-0 items-center gap-2 border-b border-border/50 px-4 py-2">
        <span className="text-sm font-medium">Workflow runs</span>
        <span className="text-xs text-muted-foreground">{runs.length}</span>
        <button
          onClick={() => void refresh()}
          className={cn(btnOutline, 'ml-auto px-2.5 py-1 text-xs')}
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center gap-2 p-8 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" /> Loading…
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 p-12 text-center text-sm text-muted-foreground">
            <Play size={26} className="opacity-40" />
            <p>No workflow runs yet.</p>
            <p className="text-xs">
              Add a workflow under <code className="font-mono">.forgejo/workflows/</code> and push to
              trigger CI.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {runs.map((r) => {
              const { Icon, cls, spin } = statusUI(r.status);
              const live = RUNNING.has(r.status);
              const dur = duration(r.run_started_at, r.updated_at, live);
              return (
                <li key={r.id} className="hover:bg-workspace-accent-5">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start gap-3 px-4 py-3"
                    title="Open run logs in Forgejo"
                  >
                    <Icon size={16} className={cn('mt-0.5 flex-shrink-0', cls, spin && 'animate-spin')} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">
                        {r.display_title || r.name}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground/80">{r.name}</span>
                        <span>#{r.run_number}</span>
                        <span>{r.event}</span>
                        <BranchChip name={r.head_branch} />
                        {r.head_sha && (
                          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">
                            {r.head_sha.slice(0, 7)}
                          </code>
                        )}
                        <span>{timeAgo(r.run_started_at || r.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2 text-xs text-muted-foreground">
                      {dur && <span className="tabular-nums">{dur}</span>}
                      <ExternalLink size={13} className="opacity-60" />
                    </div>
                  </a>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
