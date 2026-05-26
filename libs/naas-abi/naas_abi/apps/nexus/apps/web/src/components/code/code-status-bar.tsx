'use client';

import { useEffect } from 'react';
import { GitBranch } from 'lucide-react';
import { sessionDisplayTitle } from '@/lib/opencode-sessions';
import { useOpencodeSessionStore } from '@/stores/opencode-session';
import { useFilesStore } from '@/stores/files';

/** Read-only VS Code-style footer: active session label + change count. Session switching lives in the AI pane History panel. */
export function CodeStatusBar() {
  const { opencodeSessionId, ocSessions, fetchOcSessions } = useOpencodeSessionStore();
  const changeCount = Object.keys(useFilesStore((s) => s.codeDiffs)).length;

  useEffect(() => {
    void fetchOcSessions();
  }, [fetchOcSessions]);

  const currentSession = ocSessions.find((s) => s.id === opencodeSessionId);
  const label = sessionDisplayTitle(currentSession, opencodeSessionId);
  const parentSession = currentSession?.parentID
    ? ocSessions.find((s) => s.id === currentSession.parentID)
    : undefined;

  return (
    <div
      className="flex h-[22px] flex-shrink-0 select-none items-center justify-between border-t border-[#007acc]/30 bg-[#007acc] px-2 text-[11px] text-white"
      role="status"
    >
      <div
        className="flex min-w-0 max-w-[280px] items-center gap-1.5 px-1.5 py-0.5"
        title={
          parentSession
            ? `Fork of ${sessionDisplayTitle(parentSession, parentSession.id)}. Switch sessions from AI pane History.`
            : 'OpenCode session. Switch sessions from AI pane History.'
        }
      >
        <GitBranch size={12} className="flex-shrink-0 opacity-90" />
        <span className="truncate font-medium">{label}</span>
      </div>

      <div className="flex flex-shrink-0 items-center gap-3 text-[10px] text-white/85">
        {changeCount > 0 && (
          <span title="Changed files in this session">
            {changeCount} change{changeCount === 1 ? '' : 's'}
          </span>
        )}
        <span className="opacity-70">OpenCode</span>
      </div>
    </div>
  );
}
