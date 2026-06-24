'use client';

import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Code, GitBranch, GitPullRequest } from 'lucide-react';
import { cn } from '@/lib/utils';

const TABS = [
  { key: 'workspaces', label: 'Workspaces', icon: Code },
  { key: 'branches', label: 'Branches', icon: GitBranch },
  { key: 'pulls', label: 'Pull requests', icon: GitPullRequest },
] as const;

export default function CodeLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const pathname = usePathname();
  const base = `/workspace/${workspaceId}/code`;

  return (
    <div className="flex h-full flex-col">
      <nav className="flex h-11 flex-shrink-0 items-center gap-1 border-b border-border/50 px-3">
        {TABS.map((t) => {
          const href = `${base}/${t.key}`;
          const active = pathname.startsWith(href);
          const Icon = t.icon;
          return (
            <Link
              key={t.key}
              href={href}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                active
                  ? 'bg-workspace-accent-15 text-workspace-accent'
                  : 'text-muted-foreground hover:bg-workspace-accent-5',
              )}
            >
              <Icon size={15} />
              {t.label}
            </Link>
          );
        })}
      </nav>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
