'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Boxes, Code, GitPullRequest } from 'lucide-react';
import { getVertical, VERTICALS } from '@/lib/verticals';
import { AgentPanel } from '@/components/verticals/agent-panel';
import { cn } from '@/lib/utils';

export default function VerticalsPage() {
  const params = useParams();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const [activeId, setActiveId] = useState<string | null>(VERTICALS[0]?.id ?? null);
  const active = activeId ? getVertical(activeId) : null;
  const wsBase = `/workspace/${workspaceId}`;

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <Boxes size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Verticals</h1>
        <span className="text-xs text-muted-foreground">
          Locked-down apps composed over coding + agents + review
        </span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 flex-shrink-0 overflow-y-auto border-r border-border/50">
          {VERTICALS.map((v) => (
            <button
              key={v.id}
              onClick={() => setActiveId(v.id)}
              className={cn(
                'flex w-full flex-col gap-1 border-b border-border/30 px-3 py-3 text-left transition-colors hover:bg-workspace-accent-5',
                activeId === v.id && 'bg-workspace-accent-10',
              )}
            >
              <span className="text-sm font-medium">{v.title}</span>
              <span className="line-clamp-2 text-xs text-muted-foreground">{v.description}</span>
            </button>
          ))}
        </aside>

        <main className="flex-1 overflow-hidden">
          {!active ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a vertical.
            </div>
          ) : (
            <div className="flex h-full">
              <div className="flex-1 space-y-4 overflow-y-auto p-5">
                <div>
                  <h2 className="text-base font-medium">{active.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">{active.description}</p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Module: <code className="rounded bg-muted px-1 py-0.5">{active.module}</code>
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href={`${wsBase}/code/workspaces`}
                    className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                  >
                    <Code size={14} />
                    Open editor
                  </Link>
                  <Link
                    href={`${wsBase}/code/pulls`}
                    className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-workspace-accent-10"
                  >
                    <GitPullRequest size={14} />
                    Review changes
                  </Link>
                </div>
                <p className="text-xs text-muted-foreground">
                  This view is intentionally minimal: a vertical composes the same primitives the
                  full IDE uses, scoped to one module, so a non-technical user only sees what they
                  need. The agent panel on the right talks to this vertical&apos;s agent through the
                  OpenAI-compatible shim.
                </p>
              </div>
              <div className="w-96 flex-shrink-0 border-l border-border/50">
                <AgentPanel agent={active.agent} />
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
