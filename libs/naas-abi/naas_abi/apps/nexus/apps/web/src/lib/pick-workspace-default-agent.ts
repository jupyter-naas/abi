import type { FeatureKey } from '@/lib/feature-access';
import { isFeatureOfficeAgent, isNexusAbiAgent } from '@/lib/feature-office-agents';

/** Workspace default, then Abi, then first enabled.
 *
 * Abi only fills in when the workspace has no default: a workspace that
 * defaults to another orchestrator keeps it. The default still wins when
 * sync left it disabled. A stale picker id from another workspace must not
 * be the fallback.
 */
export function pickWorkspaceDefaultAgent<
  T extends { enabled?: boolean; isDefault?: boolean; class_name?: string | null },
>(agents: T[]): T | undefined {
  const defaultEnabled = agents.find((a) => a.isDefault && a.enabled);
  if (defaultEnabled) return defaultEnabled;
  const defaultAny = agents.find((a) => a.isDefault);
  if (defaultAny) return defaultAny;
  const abi = agents.find((a) => a.enabled && isNexusAbiAgent(a));
  if (abi) return abi;
  return agents.find((a) => a.enabled);
}

type OfficeAgent = {
  enabled?: boolean;
  isDefault?: boolean;
  name?: string;
  class_name?: string | null;
};

/** Enabled office agent for a feature section, or undefined. No default fallback. */
export function pickFeatureOfficeAgent<T extends OfficeAgent>(
  agents: T[],
  feature: FeatureKey | null | undefined,
): T | undefined {
  if (!feature) return undefined;
  return agents.find((agent) => agent.enabled && isFeatureOfficeAgent(agent, feature));
}

/** Right-pane agent for a route: the feature's office agent when the
 * workspace listed it, else the workspace default (Abi if there is none).
 *
 * Home, Chat, and routes with no office agent resolve to the default.
 */
export function pickFeaturePaneAgent<T extends OfficeAgent>(
  agents: T[],
  feature: FeatureKey | null | undefined,
): T | undefined {
  return pickFeatureOfficeAgent(agents, feature) ?? pickWorkspaceDefaultAgent(agents);
}

/** Nexus Slides when the workspace listed it, else the workspace default.
 *
 * The slides pane binds the office agent that owns write_slides_* tools.
 * Hardcoding Abi is wrong. Pinning the orchestrator is also wrong: that
 * agent does not have those tools and will not write the deck.
 */
export function pickSlidesOfficeAgent<T extends OfficeAgent>(agents: T[]): T | undefined {
  return pickFeaturePaneAgent(agents, 'slides');
}
