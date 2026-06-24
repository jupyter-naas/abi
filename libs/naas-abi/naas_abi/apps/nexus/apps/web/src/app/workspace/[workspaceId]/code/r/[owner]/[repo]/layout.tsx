'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Code, GitBranch, GitPullRequest, Lock, MonitorPlay, Unlock } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';
import { useCodeStore } from '@/stores/code';

export default function RepoLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const pathname = usePathname();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const owner = typeof params?.owner === 'string' ? params.owner : '';
  const repo = typeof params?.repo === 'string' ? params.repo : '';
  const repoId = owner && repo ? `${owner}/${repo}` : '';
  const repoBase = `/workspace/${workspaceId}/code/r/${repoId}`;
  const { setSelectedRepoId } = useCodeStore();
  const [meta, setMeta] = useState<{ private: boolean } | null>(null);

  // Make this repo the active selection so the reused tab views (workspaces /
  // branches / pull requests) scope to it.
  useEffect(() => {
    if (repoId) setSelectedRepoId(repoId);
  }, [repoId, setSelectedRepoId]);

  useEffect(() => {
    if (!workspaceId || !repoId) return;
    void (async () => {
      try {
        const res = await authFetch(
          `/api/coding-environments/repos?workspace_id=${encodeURIComponent(workspaceId)}`,
        );
        if (!res.ok) return;
        const repos = (await res.json()) as Array<{ repo_id: string; private: boolean }>;
        const found = repos.find((r) => r.repo_id === repoId);
        if (found) setMeta({ private: found.private });
      } catch {
        // ignore — header just omits the badge
      }
    })();
  }, [workspaceId, repoId]);

  const tabs = [
    { key: '', label: 'Code', icon: Code },
    { key: '/workspaces', label: 'Workspaces', icon: MonitorPlay },
    { key: '/branches', label: 'Branches', icon: GitBranch },
    { key: '/pulls', label: 'Pull requests', icon: GitPullRequest },
  ];

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-shrink-0 flex-col gap-2 border-b border-border/50 px-4 pt-3">
        <div className="flex items-center gap-2">
          <Link
            href={`/workspace/${workspaceId}/code/repos`}
            className="text-sm text-muted-foreground hover:underline"
          >
            Repositories
          </Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-semibold">{repoId}</span>
          {meta && (
            <span className="flex items-center gap-1 rounded-full border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              {meta.private ? <Lock size={9} /> : <Unlock size={9} />}
              {meta.private ? 'Private' : 'Public'}
            </span>
          )}
        </div>
        <nav className="-mb-px flex items-center gap-1">
          {tabs.map((t) => {
            const href = `${repoBase}${t.key}`;
            const active = t.key === '' ? pathname === repoBase : pathname.startsWith(href);
            const Icon = t.icon;
            return (
              <Link
                key={t.label}
                href={href}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'border-workspace-accent text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon size={15} />
                {t.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
