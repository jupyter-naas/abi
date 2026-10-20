/** Split ``module AgentClass`` (same form as engine ``default_agent``). */
export function parseAgentRef(
  raw: string | null | undefined,
): { moduleName: string; className: string } | null {
  const text = (raw || '').trim();
  if (!text.includes(' ')) return null;
  const moduleName = text.slice(0, text.indexOf(' ')).trim();
  const className = text.slice(text.indexOf(' ') + 1).trim();
  if (!moduleName || !className) return null;
  return { moduleName, className };
}

type AgentLike = { enabled?: boolean; class_name?: string | null };

/**
 * Match a roster agent to a config/manifest ref (``operations.counter_uas CounterUASAgent``).
 * Mirrors ``resolve_agent_ref`` in workspace_catalog_seed.py.
 */
export function pickAgentByRef<T extends AgentLike>(
  agents: T[],
  ref: string | null | undefined,
): T | undefined {
  const parsed = parseAgentRef(ref);
  if (!parsed) return undefined;
  const { moduleName, className } = parsed;
  const suffix = `/${className}`;
  const enabled = agents.filter((agent) => agent.enabled && (agent.class_name ?? '').endsWith(suffix));
  const preferred = enabled.find((agent) => {
    const classNameFull = agent.class_name ?? '';
    const modulePrefix = classNameFull.split('/')[0] ?? '';
    return (
      classNameFull === `${moduleName}/${className}` || modulePrefix.startsWith(`${moduleName}.`)
    );
  });
  if (preferred) return preferred;
  if (enabled.length === 1) return enabled[0];
  return undefined;
}
