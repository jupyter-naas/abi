'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink, Github, Loader2 } from 'lucide-react';
import Link from 'next/link';

import { RestartOsButton } from '@/components/shell/restart-os-control';
import {
  disconnectGitHub,
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
  workspaceId?: string | null;
  moduleInstalled?: boolean;
}

export function ConnectGitHubPanel({
  className,
  onConnected,
  showRestart = true,
  workspaceId = null,
  moduleInstalled,
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
      if (next.github_login) setGithubLogin(next.github_login);
      if (next.connected) setPhase('connected');
      else if (phase === 'connected') setPhase('idle');
    } catch {
      /* status is optional until user acts */
    }
  }, [phase]);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const installed = moduleInstalled ?? status?.module_installed ?? false;
  const connected = !!(status?.connected || phase === 'connected');
  const agentName = status?.agent_name || 'GitHub';
  const login = githubLogin || status?.github_login || null;
  const chatHref = workspaceId
    ? `/workspace/${workspaceId}/chat/new?agent=${encodeURIComponent(agentName)}`
    : null;
  const busy = phase === 'starting' || phase === 'polling';

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

  const handleDisconnect = async () => {
    setError(null);
    setPhase('starting');
    try {
      await disconnectGitHub();
      setGithubLogin(null);
      setUserCode(null);
      setVerificationUri(null);
      setStatus((prev) =>
        prev
          ? { ...prev, connected: false, ready: false, github_login: null }
          : { module_installed: installed, connected: false, oauth_available: true },
      );
      setPhase('idle');
      await refreshStatus();
    } catch (err) {
      setPhase('error');
      setError(err instanceof Error ? err.message : 'Failed to disconnect');
    }
  };

  return (
    <div
      className={cn(
        'space-y-3 rounded-lg border px-3 py-3 text-xs',
        connected
          ? 'border-emerald-500/40 bg-emerald-500/10'
          : 'border-border/60 bg-muted/20',
        className,
      )}
    >
      <div className="flex items-start gap-2">
        {connected ? (
          <Check size={16} className="mt-0.5 shrink-0 text-emerald-700 dark:text-emerald-300" />
        ) : (
          <Github size={16} className="mt-0.5 shrink-0" />
        )}
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">
            {connected
              ? `GitHub connected${login ? ` as @${login}` : ''}`
              : 'Connect GitHub'}
          </p>
          <p className="text-muted-foreground">
            {connected
              ? installed
                ? 'Restart OS if you just connected, then open the GitHub agent in chat.'
                : 'Credentials saved. Restart OS to load the GitHub agent.'
              : 'Authorize Abi (browser) or paste a personal access token, then restart OS.'}
          </p>
        </div>
      </div>

      {!isSuperadmin ? (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-amber-800 dark:text-amber-200">
          Connect/Disconnect require platform superadmin. You can still try; the API will reject if unauthorized.
        </p>
      ) : null}

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

      {/* Always-visible actions: Connect, Paste token, Disconnect */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || status?.oauth_available === false}
          onClick={() => void handleDeviceConnect()}
          className="inline-flex items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy && phase !== 'idle' && phase !== 'connected' && phase !== 'error' ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Github size={12} />
          )}
          {connected ? 'Connect again' : 'Connect with GitHub'}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setShowPat((v) => !v)}
          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
        >
          Paste token
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void handleDisconnect()}
          className="rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
        >
          Disconnect
        </button>
        {showRestart ? <RestartOsButton /> : null}
        {chatHref && installed ? (
          <Link
            href={chatHref}
            className="inline-flex items-center gap-1.5 rounded-md border border-workspace-accent/40 px-3 py-1.5 text-xs font-medium text-workspace-accent hover:bg-workspace-accent/10"
          >
            Open {agentName} agent
          </Link>
        ) : null}
      </div>

      {status?.oauth_available === false ? (
        <p className="text-muted-foreground">
          OAuth app not configured. Set <code className="font-mono">GITHUB_OAUTH_CLIENT_ID</code>{' '}
          in `.env`, or use Paste token.
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
