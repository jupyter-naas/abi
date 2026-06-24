'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { Check, Code, GitBranch, GitPullRequest, Plus, Star } from 'lucide-react';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { useCodeStore } from '@/stores/code';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface Repo {
  repo_id: string;
  name: string;
  default_branch: string;
}

const NAV = [
  { key: 'workspaces', label: 'Workspaces', icon: Code },
  { key: 'branches', label: 'Branches', icon: GitBranch },
  { key: 'pulls', label: 'Pull requests', icon: GitPullRequest },
] as const;

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
  const { selectedRepoId, setSelectedRepoId } = useCodeStore();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [defaultRepoId, setDefaultRepoId] = useState('');
  const codeBase = getWorkspacePath(workspaceId, '/code');
  const wsq = `workspace_id=${encodeURIComponent(workspaceId)}`;

  const fetchRepos = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const [reposRes, defRes] = await Promise.all([
        authFetch(`/api/coding-environments/repos?${wsq}`),
        authFetch(`/api/coding-environments/default-repo?${wsq}`),
      ]);
      if (defRes.ok) setDefaultRepoId(((await defRes.json()) as { repo_id?: string }).repo_id ?? '');
      if (!reposRes.ok) return;
      const data = (await reposRes.json()) as Repo[];
      setRepos(data);
      setSelectedRepoId(
        data.some((r) => r.repo_id === selectedRepoId)
          ? selectedRepoId
          : (data[0]?.repo_id ?? ''),
      );
    } catch {
      // ignore — the selector simply stays empty
    }
  }, [workspaceId, wsq, selectedRepoId, setSelectedRepoId]);

  useEffect(() => {
    void fetchRepos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  const createRepo = async () => {
    const name = window.prompt('New repository name (created empty — you can push to it):');
    if (!name?.trim()) return;
    try {
      const res = await authFetch('/api/coding-environments/repos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, name: name.trim() }),
      });
      if (res.ok) {
        const created = (await res.json()) as Repo;
        await fetchRepos();
        setSelectedRepoId(created.repo_id);
        // New repos are empty -> the Branches tab shows the push instructions.
        router.push(`${codeBase}/branches`);
      }
    } catch {
      // ignore
    }
  };

  const setAsDefault = async () => {
    if (!selectedRepoId) return;
    try {
      const res = await authFetch('/api/coding-environments/default-repo', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId, repo_id: selectedRepoId }),
      });
      if (res.ok) setDefaultRepoId(selectedRepoId);
    } catch {
      // ignore
    }
  };

  return (
    <CollapsibleSection
      id="code"
      icon={<Code size={18} />}
      label="Code"
      description="Edit, branch, and review code"
      href={getWorkspacePath(workspaceId, '/code/workspaces')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <div className="px-1 pb-2">
        <div className="mb-1 flex items-center justify-between px-1">
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Repository
          </span>
          <button
            onClick={createRepo}
            title="New repository"
            aria-label="New repository"
            className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent"
          >
            <Plus size={12} />
          </button>
        </div>
        <select
          value={selectedRepoId}
          onChange={(e) => setSelectedRepoId(e.target.value)}
          className="w-full rounded-md border border-border bg-transparent px-2 py-1.5 text-xs outline-none focus:border-workspace-accent"
        >
          {repos.length === 0 && <option value="">No repositories</option>}
          {repos.map((r) => (
            <option key={r.repo_id} value={r.repo_id}>
              {r.repo_id}
              {r.repo_id === defaultRepoId ? ' (default)' : ''}
            </option>
          ))}
        </select>
        {selectedRepoId &&
          (selectedRepoId === defaultRepoId ? (
            <p className="mt-1 flex items-center gap-1 px-1 text-[10px] text-muted-foreground">
              <Check size={11} />
              Default for new workspaces
            </p>
          ) : (
            <button
              onClick={setAsDefault}
              className="mt-1 flex items-center gap-1 px-1 text-[10px] text-muted-foreground hover:text-workspace-accent"
            >
              <Star size={11} />
              Set as default for new workspaces
            </button>
          ))}
      </div>

      <div className="space-y-0.5 px-1">
        {NAV.map((n) => {
          const href = `${codeBase}/${n.key}`;
          const active = pathname.startsWith(href);
          const Icon = n.icon;
          return (
            <button
              key={n.key}
              onClick={() => router.push(href)}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors hover:bg-workspace-accent-10',
                active
                  ? 'bg-workspace-accent-10 font-medium text-workspace-accent'
                  : 'text-foreground',
              )}
            >
              <Icon size={14} />
              {n.label}
            </button>
          );
        })}
      </div>
    </CollapsibleSection>
  );
}
