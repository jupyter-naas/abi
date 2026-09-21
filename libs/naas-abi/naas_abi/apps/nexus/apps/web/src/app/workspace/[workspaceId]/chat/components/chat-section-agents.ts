import { isNaasAbiAgent } from '@/lib/feature-office-agents';

export type ChatRosterAgent = {
  isDefault?: boolean;
  class_name?: string | null;
};

/** Upper bound on the collapsed preview, not the number of rows it shows. */
export const AGENTS_PREVIEW_COUNT = 5;

/**
 * Split a sorted roster into the rows the Chat section previews and the rows
 * it packs behind "Show N more".
 *
 * naas_abi agents are packed. Apps, Files, Ontology and the rest are bound to
 * the pane of their own section, so in the chat roster they only push the
 * agents you actually start a conversation with out of the preview. The
 * workspace default is the one exception: it is what "Auto" runs, so it stays
 * on top even when it is Abi.
 *
 * Order is preserved inside each half, so the caller's sort still decides
 * what the preview shows first.
 */
export function partitionChatRosterAgents<T extends ChatRosterAgent>(
  agents: T[],
): { preview: T[]; packed: T[] } {
  const preview: T[] = [];
  const packed: T[] = [];
  for (const agent of agents) {
    if (!agent.isDefault && isNaasAbiAgent(agent)) packed.push(agent);
    else preview.push(agent);
  }
  return { preview, packed };
}

/**
 * The rows to render and the count on the "Show N more" toggle.
 *
 * Expanding appends the packed half after the preview half, so "Show less"
 * never reorders the list. A roster that is mostly naas_abi agents therefore
 * shows fewer than `previewCount` rows while collapsed — that is the point.
 */
export function chatRosterSections<T extends ChatRosterAgent>(
  agents: T[],
  expanded: boolean,
  previewCount: number = AGENTS_PREVIEW_COUNT,
): { visible: T[]; hiddenCount: number } {
  const { preview, packed } = partitionChatRosterAgents(agents);
  const collapsed = preview.slice(0, previewCount);
  return {
    visible: expanded ? [...preview, ...packed] : collapsed,
    hiddenCount: agents.length - collapsed.length,
  };
}
