'use client';

import { useEffect, useMemo } from 'react';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { useWorkspaceStore } from '@/stores/workspace';

/** The agents of the current workspace, as the chat agent pickers list them (default first, then custom). */
export function useAgentList(searchQuery = '') {
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const { agents, fetchAgents, getAgent } = useAgentsStore();

  // The API lists exactly the agents the caller may use in the workspace.
  const usableAgents = agents;

  const filteredAgents = useMemo(
    () =>
      searchQuery.trim()
        ? usableAgents.filter(
            (a: Agent) =>
              a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
              a.description.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : usableAgents,
    [usableAgents, searchQuery]
  );

  const defaultAgents = useMemo(
    () =>
      filteredAgents
        .filter((a: Agent) => a.isDefault)
        .sort((a: Agent, b: Agent) => a.name.localeCompare(b.name)),
    [filteredAgents]
  );

  const customAgents = useMemo(
    () =>
      filteredAgents
        .filter((a: Agent) => !a.isDefault)
        .sort((a: Agent, b: Agent) => a.name.localeCompare(b.name)),
    [filteredAgents]
  );

  useEffect(() => {
    if (currentWorkspaceId) {
      fetchAgents(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchAgents]);

  return {
    usableAgents,
    defaultAgents,
    customAgents,
    filteredAgents,
    getAgent,
  } as const;
}
