/** Gatekeeper grant utilities for chat UI. */

import type { ToolCall } from '@/stores/workspace';

export interface GatekeeperDenial {
  toolName: string;
  reason: string;
  resourceType: string;
  resourceId: string;
  action: string;
}

const GATEKEEPER_DENIAL_RE =
  /Access denied by gatekeeper:\s*(?<reason>[^.]+)\./i;

const MISSING_GRANT_RE =
  /^missing_grant:(?<type>[^:]+):(?<id>[^:]+):(?<action>.+)$/;

export function parseMissingGrantReason(reason: string): Omit<GatekeeperDenial, 'toolName'> | null {
  const match = reason.trim().match(MISSING_GRANT_RE);
  if (!match?.groups) return null;
  const { type, id, action } = match.groups;
  if (!type || !id || !action) return null;
  return {
    reason,
    resourceType: type,
    resourceId: id,
    action,
  };
}

export function parseGatekeeperDenialFromOutput(
  output: string,
  toolName?: string,
): GatekeeperDenial | null {
  const match = output.match(GATEKEEPER_DENIAL_RE);
  if (!match?.groups?.reason) return null;
  const parsed = parseMissingGrantReason(match.groups.reason);
  if (!parsed) return null;
  return {
    toolName: toolName ?? 'tool',
    ...parsed,
  };
}

export function extractGatekeeperDenialFromToolCalls(
  toolCalls: ToolCall[] | undefined,
): GatekeeperDenial | null {
  if (!toolCalls?.length) return null;
  for (let i = toolCalls.length - 1; i >= 0; i -= 1) {
    const call = toolCalls[i];
    if (!call.output) continue;
    const denial = parseGatekeeperDenialFromOutput(
      call.output,
      call.rawName || call.toolName,
    );
    if (denial) return denial;
  }
  return null;
}

export function describeGatekeeperAction(action: string): string {
  switch (action) {
    case 'read_secrets':
      return 'read repository secrets';
    case 'delete_repo':
      return 'delete repositories';
    case 'export':
      return 'export conversations containing sensitive data';
    default:
      return action.replace(/_/g, ' ');
  }
}

export function describeGatekeeperResource(type: string, id: string): string {
  if (type === 'github.repo') {
    return `GitHub repository ${id}`;
  }
  if (type === 'github.org') {
    return `GitHub organization ${id}`;
  }
  return `${type} ${id}`;
}
