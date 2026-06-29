'use client';

// Shared primitives + helpers for the GitHub-style pull-request views.
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { GitMerge, GitPullRequest, GitPullRequestClosed } from 'lucide-react';
import { cn } from '@/lib/utils';

// ---- Types (mirror the /api/code-review/* response shapes) ----------------

export interface Proposal {
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

export interface Comment {
  id: string;
  path: string | null;
  line: number | null;
  body: string;
  author: string;
  created_at: string | null;
}

export interface Review {
  id: string;
  state: string; // approved | changes_requested | comment | pending
  body: string;
  author: string;
  submitted_at: string | null;
}

export interface DiffFile {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  patch?: string | null;
  old_path?: string | null;
}

export interface CommitItem {
  sha: string;
  message: string;
  author: string;
  date: string | null;
}

export interface Branch {
  name: string;
  protected: boolean;
}

// ---- HTTP helper -----------------------------------------------------------

export async function readJson<T>(res: Response): Promise<T> {
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

export function timeAgo(iso: string | null | undefined): string {
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

// ---- Avatar ----------------------------------------------------------------

const AVATAR_COLORS = [
  'bg-rose-500',
  'bg-orange-500',
  'bg-amber-500',
  'bg-emerald-500',
  'bg-teal-500',
  'bg-sky-500',
  'bg-indigo-500',
  'bg-violet-500',
  'bg-fuchsia-500',
];

function colorFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

export function Avatar({ name, size = 20 }: { name: string; size?: number }) {
  const initial = (name || '?').trim().charAt(0).toUpperCase() || '?';
  return (
    <span
      className={cn(
        'inline-flex flex-shrink-0 items-center justify-center rounded-full font-semibold text-white',
        colorFor(name || '?'),
      )}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.5) }}
      title={name}
    >
      {initial}
    </span>
  );
}

// ---- State badge -----------------------------------------------------------

export function StateBadge({ state, size = 'md' }: { state: string; size?: 'sm' | 'md' }) {
  const cfg =
    state === 'merged'
      ? { tone: 'bg-violet-500/15 text-violet-600', Icon: GitMerge, label: 'Merged' }
      : state === 'closed'
        ? { tone: 'bg-red-500/15 text-red-600', Icon: GitPullRequestClosed, label: 'Closed' }
        : { tone: 'bg-emerald-500/15 text-emerald-600', Icon: GitPullRequest, label: 'Open' };
  const { tone, Icon, label } = cfg;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium',
        tone,
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
      )}
    >
      <Icon size={size === 'sm' ? 11 : 13} />
      {label}
    </span>
  );
}

// ---- Branch chip -----------------------------------------------------------

export function BranchChip({ name }: { name: string }) {
  return (
    <code className="rounded bg-workspace-accent-10 px-1.5 py-0.5 font-mono text-[11px] text-foreground">
      {name}
    </code>
  );
}

// ---- Markdown --------------------------------------------------------------

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0 [&_pre]:my-2 [&_h1]:text-base [&_h2]:text-sm [&_code]:rounded [&_code]:bg-background/60 [&_code]:px-1 [&_code]:text-xs">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

// ---- Diff viewer (salvaged + line numbers) ---------------------------------

function parseHunkStart(line: string): { oldLn: number; newLn: number } | null {
  // @@ -a,b +c,d @@
  const m = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
  if (!m) return null;
  return { oldLn: parseInt(m[1], 10), newLn: parseInt(m[2], 10) };
}

export function DiffViewer({ files }: { files: DiffFile[] }) {
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
            <div className="overflow-x-auto font-mono text-[12px] leading-[1.5]">
              {(() => {
                let oldLn = 0;
                let newLn = 0;
                return f.patch.split('\n').map((line, i) => {
                  const hunk = parseHunkStart(line);
                  if (hunk) {
                    oldLn = hunk.oldLn;
                    newLn = hunk.newLn;
                    return (
                      <div
                        key={i}
                        className="flex bg-workspace-accent-5 text-muted-foreground"
                      >
                        <span className="w-[5.5rem] flex-shrink-0 select-none" />
                        <span className="whitespace-pre px-2">{line}</span>
                      </div>
                    );
                  }
                  const isAdd = line.startsWith('+');
                  const isDel = line.startsWith('-');
                  const tone = isAdd
                    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                    : isDel
                      ? 'bg-red-500/10 text-red-700 dark:text-red-400'
                      : 'text-foreground';
                  const oldCell = isAdd ? '' : String(oldLn);
                  const newCell = isDel ? '' : String(newLn);
                  if (!isAdd) oldLn += 1;
                  if (!isDel) newLn += 1;
                  return (
                    <div key={i} className={cn('flex', tone)}>
                      <span className="flex w-[5.5rem] flex-shrink-0 select-none border-r border-border/40 text-right text-[10px] text-muted-foreground/70">
                        <span className="w-1/2 px-1">{oldCell}</span>
                        <span className="w-1/2 px-1">{newCell}</span>
                      </span>
                      <span className="whitespace-pre px-2">{line || ' '}</span>
                    </div>
                  );
                });
              })()}
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

// ---- Small buttons ---------------------------------------------------------

export const btnPrimary =
  'inline-flex items-center justify-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50';
export const btnOutline =
  'inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-workspace-accent-10 disabled:opacity-50';
