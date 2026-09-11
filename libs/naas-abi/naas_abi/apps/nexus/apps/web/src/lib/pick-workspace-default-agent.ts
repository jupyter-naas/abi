/** Workspace default, then first enabled. No Abi-first override.
 *
 * The default still wins when sync left it disabled. A stale picker id from
 * another workspace must not be the fallback.
 */
export function pickWorkspaceDefaultAgent<
  T extends { enabled?: boolean; isDefault?: boolean },
>(agents: T[]): T | undefined {
  const defaultEnabled = agents.find((a) => a.isDefault && a.enabled);
  if (defaultEnabled) return defaultEnabled;
  const defaultAny = agents.find((a) => a.isDefault);
  if (defaultAny) return defaultAny;
  return agents.find((a) => a.enabled);
}

type SlidesOfficeAgent = {
  enabled?: boolean;
  isDefault?: boolean;
  name?: string;
  class_name?: string | null;
};

function isNexusSlidesAgent(agent: SlidesOfficeAgent): boolean {
  if (agent.name === 'Slides') return true;
  const className = agent.class_name ?? '';
  return className.endsWith('/SlidesAgent') && className.includes('naas_abi');
}

/** Nexus Slides when the workspace listed it, else the workspace default.
 *
 * The slides pane binds the office agent that owns write_slides_* tools.
 * Hardcoding Abi is wrong. Pinning the orchestrator is also wrong: that
 * agent does not have those tools and will not write the deck.
 */
export function pickSlidesOfficeAgent<T extends SlidesOfficeAgent>(
  agents: T[],
): T | undefined {
  const slides = agents.find((agent) => agent.enabled && isNexusSlidesAgent(agent));
  return slides ?? pickWorkspaceDefaultAgent(agents);
}

type DocumentsOfficeAgent = {
  enabled?: boolean;
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
  const documents = agents.find((agent) => agent.enabled && isNexusDocumentsAgent(agent));
  return documents ?? pickWorkspaceDefaultAgent(agents);
}

/** Right-pane office bind: Slides on a deck, Documents on a file, else default. */
export function pickPaneOfficeAgent<
  T extends SlidesOfficeAgent & DocumentsOfficeAgent,
>(
  agents: T[],
  surface: { onSlides?: boolean; onDocuments?: boolean },
): T | undefined {
  if (surface.onDocuments) return pickDocumentsOfficeAgent(agents);
  if (surface.onSlides) return pickSlidesOfficeAgent(agents);
  return pickWorkspaceDefaultAgent(agents);
}
