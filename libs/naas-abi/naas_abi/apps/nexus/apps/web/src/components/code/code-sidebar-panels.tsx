'use client';

import { useCallback, useEffect } from 'react';
import { FileCode } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOpencodeSessionStore } from '@/stores/opencode-session';
import { resolveCodePath, useFilesStore } from '@/stores/files';

const STATUS_LABEL: Record<string, string> = {
  added: 'A',
  modified: 'M',
  deleted: 'D',
  renamed: 'R',
};

export function OpencodeChangesList({ onOpenFile }: { onOpenFile: (path: string) => void }) {
  const { opencodeSessionId, fetchSessionDiff } = useOpencodeSessionStore();
  const { codeDiffs, localChanges, codeRoot } = useFilesStore();

  useEffect(() => {
    void fetchSessionDiff(opencodeSessionId);
  }, [opencodeSessionId, fetchSessionDiff]);

  // Merge: OpenCode diffs take precedence; local changes fill the gaps.
  const merged: Record<string, { status: string; additions?: number; deletions?: number; local?: boolean }> = {};
  for (const [file, info] of Object.entries(localChanges)) {
    merged[file] = { status: info.status, local: true };
  }
  for (const [file, info] of Object.entries(codeDiffs)) {
    merged[file] = { status: info.status, additions: info.additions, deletions: info.deletions };
  }
  const diffEntries = Object.entries(merged).sort(([a], [b]) => a.localeCompare(b));

  const resolveDiffPath = useCallback(
    (file: string) => {
      if (codeRoot && file.startsWith(codeRoot)) return file;
      if (file.startsWith('/')) return file;
      return resolveCodePath(file);
    },
    [codeRoot],
  );

  if (diffEntries.length === 0) {
    return (
      <p className="px-2 py-1 text-[11px] italic text-muted-foreground">
        No changes in this session
      </p>
    );
  }

  return (
    <div className="space-y-0.5 overflow-y-auto">
      {diffEntries.map(([file, diff]) => {
        const filename = file.split('/').pop() || file;
        const badge = STATUS_LABEL[diff.status] ?? 'M';
        return (
          <button
            key={file}
            type="button"
            onClick={() => onOpenFile(resolveDiffPath(file))}
            className="group flex w-full items-center gap-1 rounded-md py-[3px] pl-1.5 pr-1 text-left text-xs hover:bg-workspace-accent-10"
            title={file}
          >
            <span
              className={cn(
                'w-3 flex-shrink-0 text-center font-mono text-[9px] font-bold',
                diff.status === 'added' && 'text-emerald-500',
                diff.status === 'modified' && 'text-amber-500',
                diff.status === 'deleted' && 'text-red-500',
              )}
            >
              {badge}
            </span>
            <FileCode size={11} className="flex-shrink-0 text-muted-foreground" />
            <span
              className={cn(
                'min-w-0 flex-1 truncate',
                diff.status === 'added' && 'text-emerald-500 dark:text-emerald-400',
                diff.status === 'modified' && 'text-amber-500 dark:text-amber-400',
                diff.status === 'deleted' && 'text-red-500 line-through opacity-60',
              )}
            >
              {filename}
            </span>
            <span className="ml-1 flex-shrink-0 font-mono text-[9px] leading-none opacity-80">
              {(diff.additions ?? 0) > 0 && (
                <span className="text-emerald-500">+{diff.additions}</span>
              )}
              {(diff.deletions ?? 0) > 0 && (
                <span className="ml-0.5 text-red-400">-{diff.deletions}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
