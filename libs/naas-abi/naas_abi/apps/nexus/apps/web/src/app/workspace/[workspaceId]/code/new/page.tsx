'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { BookMarked, Loader2, Lock, Unlock } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';

export default function NewRepoPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const codeBase = `/workspace/${workspaceId}/code`;

  const [name, setName] = useState('');
  const [isPrivate, setIsPrivate] = useState(true);
  const [autoInit, setAutoInit] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = /^[a-zA-Z0-9._-]+$/.test(name);

  const create = async () => {
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch('/api/coding-environments/repos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          name,
          private: isPrivate,
          auto_init: autoInit,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body?.detail || `Failed (${res.status})`);
      }
      const created = (await res.json()) as { repo_id: string };
      router.push(`${codeBase}/r/${created.repo_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4">
        <BookMarked size={18} className="text-workspace-accent" />
        <h1 className="text-sm font-medium">Create a new repository</h1>
      </header>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-xl space-y-5">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Repository name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-project"
              autoFocus
              className="w-full rounded-md border border-border bg-transparent px-3 py-2 text-sm outline-none focus:border-workspace-accent"
            />
            {name && !valid && (
              <span className="text-xs text-red-600">
                Use only letters, numbers, and . _ -
              </span>
            )}
          </label>

          <div className="space-y-2">
            <span className="text-sm font-medium">Visibility</span>
            {[
              { v: true, icon: <Lock size={15} />, label: 'Private', desc: 'Only you and collaborators can see it.' },
              { v: false, icon: <Unlock size={15} />, label: 'Public', desc: 'Anyone in this Forgejo can see it.' },
            ].map((o) => (
              <button
                key={o.label}
                onClick={() => setIsPrivate(o.v)}
                className={cn(
                  'flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors',
                  isPrivate === o.v
                    ? 'border-workspace-accent bg-workspace-accent-5'
                    : 'border-border hover:bg-workspace-accent-5',
                )}
              >
                <span className="mt-0.5 text-muted-foreground">{o.icon}</span>
                <span>
                  <span className="block text-sm font-medium">{o.label}</span>
                  <span className="block text-xs text-muted-foreground">{o.desc}</span>
                </span>
              </button>
            ))}
          </div>

          <label className="flex items-start gap-3 rounded-md border border-border p-3">
            <input
              type="checkbox"
              checked={autoInit}
              onChange={(e) => setAutoInit(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="block text-sm font-medium">Initialize with a README</span>
              <span className="block text-xs text-muted-foreground">
                Leave unchecked to create an empty repo and push your existing code to it.
              </span>
            </span>
          </label>

          <div className="flex items-center gap-2">
            <button
              onClick={create}
              disabled={busy || !valid}
              className="flex items-center gap-2 rounded-md bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              Create repository
            </button>
            <button
              onClick={() => router.push(`${codeBase}/repos`)}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-workspace-accent-10"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
