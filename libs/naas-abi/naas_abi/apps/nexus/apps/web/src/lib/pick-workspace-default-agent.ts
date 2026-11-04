import type { FeatureKey } from '@/lib/feature-access';
import { isFeatureOfficeAgent, isNexusAbiAgent } from '@/lib/feature-office-agents';

/** Workspace default, then Abi, then the first agent listed.
 *
 * The API lists exactly the agents the caller may use, so every one listed is
 * usable. Abi only fills in when the workspace has no default: a workspace that
 * defaults to another orchestrator keeps it. A stale picker id from another
 * workspace must not be the fallback.
 */
export function pickWorkspaceDefaultAgent<
  T extends { isDefault?: boolean; class_name?: string | null },
>(agents: T[]): T | undefined {
  const defaultAgent = agents.find((a) => a.isDefault);
  if (defaultAgent) return defaultAgent;
  const abi = agents.find((a) => isNexusAbiAgent(a));
  if (abi) return abi;
  return agents[0];
}

type OfficeAgent = {
  isDefault?: boolean;
  name?: string;
  class_name?: string | null;
};

/** The office agent of a feature section, when listed, or undefined. No default fallback. */
export function pickFeatureOfficeAgent<T extends OfficeAgent>(
  agents: T[],
  feature: FeatureKey | null | undefined,
): T | undefined {
  if (!feature) return undefined;
  return agents.find((agent) => isFeatureOfficeAgent(agent, feature));
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

type DocumentsOfficeAgent = {
  isDefault?: boolean;
  name?: string;
  class_name?: string | null;
};

export function isNexusDocumentsAgent(agent: DocumentsOfficeAgent): boolean {
  if (agent.name === 'Documents') return true;
  const className = agent.class_name ?? '';
  return className.endsWith('/DocumentsAgent') && className.includes('naas_abi');
}

/** Nexus Documents when the workspace listed it, else the workspace default. */
export function pickDocumentsOfficeAgent<T extends DocumentsOfficeAgent>(
  agents: T[],
): T | undefined {
  const documents = agents.find((agent) => isNexusDocumentsAgent(agent));
  return documents ?? pickWorkspaceDefaultAgent(agents);
}

function isNexusSheetsAgent(agent: OfficeAgent): boolean {
  if (agent.name === 'Sheets') return true;
  const className = agent.class_name ?? '';
  return className.endsWith('/SheetsAgent') && className.includes('naas_abi');
}

/** Nexus Sheets when the workspace listed it, else the workspace default. */
export function pickSheetsOfficeAgent<T extends OfficeAgent>(
  agents: T[],
): T | undefined {
  const sheets = agents.find((agent) => isNexusSheetsAgent(agent));
  return sheets ?? pickWorkspaceDefaultAgent(agents);
}

/** Right-pane office bind: Sheets/Documents/Slides on that surface, else default. */
export function pickPaneOfficeAgent<
  T extends OfficeAgent & DocumentsOfficeAgent,
>(
  agents: T[],
  surface: { onSlides?: boolean; onDocuments?: boolean; onSheets?: boolean },
): T | undefined {
  if (surface.onSheets) return pickSheetsOfficeAgent(agents);
  if (surface.onDocuments) return pickDocumentsOfficeAgent(agents);
  if (surface.onSlides) return pickSlidesOfficeAgent(agents);
  return pickWorkspaceDefaultAgent(agents);
}

/** Office surface from the route segment, not leftover store slugs or slug text. */
export function officeSurfaceFromPath(pathname: string | null | undefined): {
  onSlides: boolean;
  onDocuments: boolean;
  onSheets: boolean;
} {
  const parts = (pathname || '').split(/[?#]/)[0].split('/').filter(Boolean);
  const workspaceIndex = parts.indexOf('workspace');
  const feature = workspaceIndex >= 0 ? parts[workspaceIndex + 2] : '';
  return {
    onSlides: feature === 'slides',
    onDocuments: feature === 'documents',
    onSheets: feature === 'sheets',
  };
}
