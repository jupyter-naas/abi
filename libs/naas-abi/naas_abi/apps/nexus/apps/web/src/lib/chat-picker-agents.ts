export type ChatPickerAgent = { id: string; inChatPicker?: boolean };

/**
 * The agents a chat picker, or the Chat section's roster, offers.
 *
 * The API marks `in_chat_picker: false` the agents the workspace default
 * fronts (an Abi specialization with `fronts_its_agents`: Abi and every agent
 * it hands work to). Chat reaches them through the default. The store keeps
 * them, because a section's pane still binds its own: `keepIds` are the
 * agents a pane picker must still offer (the one it runs, the section's).
 */
export function chatPickerAgents<T extends ChatPickerAgent>(
  agents: T[],
  keepIds: ReadonlyArray<string | null | undefined> = [],
): T[] {
  const kept = new Set(keepIds.filter((id): id is string => Boolean(id)));
  return agents.filter((agent) => agent.inChatPicker !== false || kept.has(agent.id));
}
