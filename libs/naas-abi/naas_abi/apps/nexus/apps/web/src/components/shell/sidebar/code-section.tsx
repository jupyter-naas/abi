'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { BookMarked, Code, Lock, Plus, Unlock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface Repo {
  repo_id: string;
  name: string;
  private: boolean;
}

export function CodeSection({
  collapsed,
  detailOnly,
}: {
  collapsed: boolean;
  detailOnly?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const codeBase = getWorkspacePath(workspaceId, '/code');
  const [repos, setRepos] = useState<Repo[]>([]);

  const fetchRepos = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await authFetch(
        `/api/coding-environments/repos?workspace_id=${encodeURIComponent(workspaceId)}`,
      );
      if (res.ok) setRepos((await res.json()) as Repo[]);
    } catch {
      // ignore
    }
  }, [workspaceId]);

  useEffect(() => {
    void fetchRepos();
  }, [fetchRepos]);

  return (
    <CollapsibleSection
      id="code"
      icon={<Code size={18} />}
      label="Code"
      description="Repositories, workspaces and reviews"
      href={getWorkspacePath(workspaceId, '/code/repos')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="flex items-center justify-between px-1 pb-1">
        <button
          onClick={() => router.push(`${codeBase}/repos`)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium hover:bg-workspace-accent-10',
            pathname === `${codeBase}/repos` && 'text-workspace-accent',
          )}
        >
          <BookMarked size={13} />
          All repositories
        </button>
        <button
          onClick={() => router.push(`${codeBase}/new`)}
          title="New repository"
          aria-label="New repository"
          className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent"
        >
          <Plus size={13} />
        </button>
      </div>

      <div className="space-y-0.5 px-1">
        <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Repositories
        </div>
        {repos.length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground">No repositories</p>
        ) : (
          repos.map((r) => {
            const href = `${codeBase}/r/${r.repo_id}`;
            const active = pathname.startsWith(href);
            return (
              <button
                key={r.repo_id}
                onClick={() => router.push(href)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors hover:bg-workspace-accent-10',
                  active ? 'bg-workspace-accent-10 font-medium text-workspace-accent' : 'text-foreground',
                )}
              >
                {r.private ? (
                  <Lock size={11} className="flex-shrink-0 text-muted-foreground" />
                ) : (
                  <Unlock size={11} className="flex-shrink-0 text-muted-foreground" />
                )}
                <span className="truncate">{r.repo_id}</span>
              </button>
            );
          })
        )}
      </div>
    </CollapsibleSection>
  );
}
