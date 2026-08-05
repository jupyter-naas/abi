'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink, Github, Loader2 } from 'lucide-react';

import { RestartOsButton } from '@/components/shell/restart-os-control';
import {
  fetchGitHubConnectStatus,
  saveGitHubPersonalAccessToken,
  startGitHubDeviceFlow,
  waitForGitHubDeviceAuth,
  type GitHubConnectStatus,
} from '@/lib/github-connect';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

type Phase =
  | 'idle'
  | 'starting'
  | 'awaiting_user'
  | 'polling'
  | 'connected'
  | 'error';

interface ConnectGitHubPanelProps {
  className?: string;
  onConnected?: () => void;
  showRestart?: boolean;
}

export function ConnectGitHubPanel({
  className,
  onConnected,
  showRestart = true,
}: ConnectGitHubPanelProps) {
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);
  const [status, setStatus] = useState<GitHubConnectStatus | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [userCode, setUserCode] = useState<string | null>(null);
  const [verificationUri, setVerificationUri] = useState<string | null>(null);
  const [githubLogin, setGithubLogin] = useState<string | null>(null);
  const [pat, setPat] = useState('');
  const [showPat, setShowPat] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await fetchGitHubConnectStatus();
      setStatus(next);
      if (next.connected) {
        setPhase('connected');
      }
    } catch {
      /* optional until user interacts */
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const handleDeviceConnect = async () => {
    setError(null);
    setPhase('starting');
    try {
      const start = await startGitHubDeviceFlow();
      setUserCode(start.user_code);
      setVerificationUri(start.verification_uri);
      setPhase('awaiting_user');
      window.open(start.verification_uri, '_blank', 'noopener,noreferrer');
      setPhase('polling');
      const result = await waitForGitHubDeviceAuth(start.session_id, start.interval);
      if (result.status !== 'complete' || !result.connected) {
        throw new Error(result.detail || 'GitHub authorization was not completed');
      }
      setGithubLogin(result.github_login ?? null);
      setPhase('connected');
      await refreshStatus();
      onConnected?.();
    } catch (err) {
      setPhase('error');
      setError(err instanceof Error ? err.message : 'GitHub connect failed');
    }
  };

  const handlePatSave = async () => {
    setError(null);
    setPhase('starting');
    try {
      const result = await saveGitHubPersonalAccessToken(pat);
      setGithubLogin(result.github_login ?? null);
      setPat('');
      setShowPat(false);
      setPhase('connected');
      await refreshStatus();
      onConnected?.();
    } catch (err) {
      setPhase('error');
      setError(err instanceof Error ? err.message : 'Failed to save token');
    }
  };

  if (!isSuperadmin) {
    return (
      <div className={cn('rounded-lg border border-border/60 bg-muted/30 px-3 py-2 text-xs text-muted-foreground', className)}>
        Ask a platform admin to connect GitHub for this Abi instance.
      </div>
    );
  }

  if (status?.connected || phase === 'connected') {
    return (
      <div className={cn('space-y-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-3 text-xs', className)}>
        <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-200">
          <Check size={14} />
          <span>
            GitHub connected{githubLogin ? ` as @${githubLogin}` : ''}.
            {status?.module_installed
              ? ' Restart OS to apply credentials.'
              : ' Install the GitHub module, then restart OS.'}
          </span>
        </div>
        {showRestart ? <RestartOsButton /> : null}
      </div>
    );
  }

  const busy = phase === 'starting' || phase === 'polling';

  return (
    <div className={cn('space-y-3 rounded-lg border border-border/60 bg-muted/20 px-3 py-3 text-xs', className)}>
      <div className="flex items-start gap-2">
        <Github size={16} className="mt-0.5 shrink-0" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">Connect GitHub</p>
          <p className="text-muted-foreground">
            Authorize Abi on GitHub — a browser tab opens for login and approval. Credentials
            are saved automatically; then restart OS.
          </p>
        </div>
      </div>

      {(phase === 'awaiting_user' || phase === 'polling') && userCode ? (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
          <p className="text-muted-foreground">
            Confirm code <span className="font-mono font-semibold text-foreground">{userCode}</span>{' '}
            on GitHub if prompted.
          </p>
          {verificationUri ? (
            <a
              href={verificationUri}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-workspace-accent hover:underline"
            >
              Open GitHub authorization
              <ExternalLink size={12} />
            </a>
          ) : null}
          {phase === 'polling' ? (
            <p className="mt-2 inline-flex items-center gap-1 text-muted-foreground">
              <Loader2 size={12} className="animate-spin" />
              Waiting for authorization…
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || status?.oauth_available === false}
          onClick={() => void handleDeviceConnect()}
          className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Github size={12} />}
          Connect with GitHub
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setShowPat((v) => !v)}
          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50"
        >
          Paste token
        </button>
      </div>

      {status?.oauth_available === false ? (
        <p className="text-muted-foreground">
          OAuth app not configured — set <code className="font-mono">GITHUB_OAUTH_CLIENT_ID</code>{' '}
          in `.env`, or paste a personal access token below.
        </p>
      ) : null}

      {showPat ? (
        <div className="space-y-2">
          <input
            type="password"
            value={pat}
            onChange={(e) => setPat(e.target.value)}
            placeholder="ghp_…"
            className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
          />
          <button
            type="button"
            disabled={!pat.trim() || busy}
            onClick={() => void handlePatSave()}
            className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50"
          >
            Save token
          </button>
        </div>
      ) : null}

      {error ? <p className="text-destructive">{error}</p> : null}
    </div>
  );
}
