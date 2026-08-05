'use client';

import { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, ShieldAlert } from 'lucide-react';

import {
  describeGatekeeperAction,
  describeGatekeeperResource,
  extractGatekeeperDenialFromToolCalls,
  type GatekeeperDenial,
} from '@/lib/gatekeeper';
import { useGatekeeperStore } from '@/stores/gatekeeper';
import type { ToolCall } from '@/stores/workspace';

type GrantState = 'idle' | 'granting' | 'granted' | 'continuing' | 'error';

interface GatekeeperGrantBannerProps {
  conversationId: string;
  workspaceId: string | null;
  toolCalls?: ToolCall[];
  liveDenial?: GatekeeperDenial | null;
  onContinueAfterGrant?: (conversationId: string) => void | Promise<void>;
}

export function GatekeeperGrantBanner({
  conversationId,
  workspaceId,
  toolCalls,
  liveDenial,
  onContinueAfterGrant,
}: GatekeeperGrantBannerProps) {
  const grantConversation = useGatekeeperStore((s) => s.grantConversation);
  const hasGrant = useGatekeeperStore((s) => s.hasGrant);
  const fetchGrants = useGatekeeperStore((s) => s.fetchGrants);

  const denial = useMemo(() => {
    if (liveDenial) return liveDenial;
    return extractGatekeeperDenialFromToolCalls(toolCalls);
  }, [liveDenial, toolCalls]);

  const [grantState, setGrantState] = useState<GrantState>('idle');
  const [grantError, setGrantError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!workspaceId || !conversationId) return;
    fetchGrants(workspaceId, conversationId).catch(() => {
      /* grants are optional until user interacts */
    });
  }, [workspaceId, conversationId, fetchGrants]);

  useEffect(() => {
    setDismissed(false);
    setGrantState('idle');
    setGrantError(null);
  }, [denial?.resourceType, denial?.resourceId, denial?.action, conversationId]);

  if (!denial || dismissed || !workspaceId) {
    return null;
  }

  const alreadyGranted = hasGrant(
    conversationId,
    denial.resourceType,
    denial.resourceId,
    denial.action,
  );

  if (alreadyGranted || grantState === 'granted' || grantState === 'continuing') {
    const continuing = grantState === 'continuing';
    return (
      <div className="mb-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-800 dark:text-emerald-200">
        <div className="flex items-center gap-2">
          {continuing ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Check size={14} />
          )}
          <span>
            {continuing
              ? 'Access granted — continuing with your request…'
              : `Access granted for ${describeGatekeeperResource(denial.resourceType, denial.resourceId)}.`}
          </span>
        </div>
      </div>
    );
  }

  const handleGrant = async () => {
    setGrantState('granting');
    setGrantError(null);
    try {
      await grantConversation(workspaceId, conversationId, {
        resourceType: denial.resourceType,
        resourceId: denial.resourceId,
        actions: [denial.action],
      });
      setGrantState('granted');
      if (onContinueAfterGrant) {
        setGrantState('continuing');
        await onContinueAfterGrant(conversationId);
      }
    } catch (err) {
      setGrantError(err instanceof Error ? err.message : 'Failed to grant access');
      setGrantState('error');
    }
  };

  return (
    <div className="mb-3 rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-3 text-xs text-foreground">
      <div className="flex items-start gap-2">
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="text-sm font-medium">Approval required</p>
          <p className="text-muted-foreground">
            To continue, the agent needs permission to{' '}
            {describeGatekeeperAction(denial.action)} on{' '}
            {describeGatekeeperResource(denial.resourceType, denial.resourceId)}.
            {denial.toolName ? (
              <>
                {' '}
                This applies to{' '}
                <span className="font-mono text-foreground/80">{denial.toolName}</span>.
              </>
            ) : null}
          </p>
          <p className="text-muted-foreground/80">
            Grant access for this chat only — the agent will pick up where it left off.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleGrant()}
              disabled={grantState === 'granting'}
              className="rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {grantState === 'granting' ? (
                <span className="inline-flex items-center gap-1">
                  <Loader2 size={12} className="animate-spin" />
                  Granting…
                </span>
              ) : (
                'Grant access & continue'
              )}
            </button>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50"
            >
              Not now
            </button>
          </div>
          {grantError ? <p className="text-destructive">{grantError}</p> : null}
        </div>
      </div>
    </div>
  );
}
