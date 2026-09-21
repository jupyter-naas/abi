import type { FeatureKey } from '@/lib/feature-access';
import { pickAgentByRef } from '@/lib/parse-agent-ref';
import { pickFeaturePaneAgent } from '@/lib/pick-workspace-default-agent';
import { useAgentsStore } from '@/stores/agents';
import { useWorkspaceStore } from '@/stores/workspace';

/** Bind the right pane to the agent of a section (the Slides rule, generalized).
 *
 * Picks the feature's office agent when the workspace lists it, else the
 * workspace default (Abi when there is none). Home, Chat, and sections
 * without an agent always get the default. An explicit picker choice
 * survives unless `force`: callers force when an item is open (deck, app,
 * ...) because an agent without the feature's tools burns the turn on
 * transfers.
 */
export function pickPaneAgentForSurface(
  agents: ReturnType<typeof useAgentsStore.getState>['agents'],
  surface: FeatureKey | null,
  appAgentRef?: string | null,
) {
  if (surface === 'apps' && appAgentRef) {
    const appAgent = pickAgentByRef(agents, appAgentRef);
    if (appAgent) return appAgent;
  }
  return pickFeaturePaneAgent(agents, surface);
}

export function bindFeaturePaneAgent(
  surface: FeatureKey | null,
  opts?: { force?: boolean; appAgentRef?: string | null },
): string | null {
  const ws = useWorkspaceStore.getState();
  const agents = useAgentsStore.getState().agents;
  const target = pickPaneAgentForSurface(agents, surface, opts?.appAgentRef);
  if (!target) return null;
  const currentStillValid = Boolean(
    ws.paneAgent && agents.some((a) => a.enabled && a.id === ws.paneAgent),
  );
  if (opts?.force || !ws.paneAgentExplicitlySelected || !currentStillValid) {
    ws.setPaneAgent(target.id);
  }
  return target.id;
}

/** Open the right pane on a section with its agent bound.
 *
 * `freshChat` starts a blank pane thread and drops the picker choice.
 * `resourceId` (the open deck, app, ...) forces the office agent.
 */
export function openFeatureAgentPane(
  surface: FeatureKey,
  opts?: { freshChat?: boolean; resourceId?: string | null; appAgentRef?: string | null },
): string | null {
  const ws = useWorkspaceStore.getState();
  ws.setContextPanelOpen(true);
  if (opts?.freshChat) {
    ws.setPaneConversationId(null);
    ws.clearPaneAgentExplicitSelection();
  }
  return bindFeaturePaneAgent(surface, {
    force: Boolean(opts?.resourceId) || Boolean(opts?.freshChat),
    appAgentRef: opts?.appAgentRef,
  });
}
