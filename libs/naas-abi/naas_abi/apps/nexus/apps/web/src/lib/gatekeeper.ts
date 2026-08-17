/** Gatekeeper grant utilities for chat UI. */

import type { ToolCall } from '@/stores/workspace';

export interface GatekeeperDenial {
  toolName: string;
  reason: string;
  resourceType: string;
  resourceId: string;
  action: string;
}

const GATEKEEPER_APPROVAL_RE =
  /Gatekeeper approval required:\s*(?<reason>[^.]+)\./i;

const GATEKEEPER_DENIAL_RE =
  /Access denied by gatekeeper:\s*(?<reason>[^.]+)\./i;

const MISSING_GRANT_RE =
  /^missing_grant:(?<type>[^:]+):(?<id>[^:]+):(?<action>.+)$/;

const MISSING_GRANT_INLINE_RE =
  /missing_grant:(?<type>[^:]+):(?<id>[^:]+):(?<action>[a-z0-9_*]+)/i;

export function parseMissingGrantReason(
  reason: string,
): Omit<GatekeeperDenial, 'toolName'> | null {
  const trimmed = reason.trim();
  const inline = trimmed.match(MISSING_GRANT_INLINE_RE);
  if (inline?.groups) {
    const { type, id, action } = inline.groups;
    if (type && id && action) {
      return {
        reason: inline[0],
        resourceType: type,
        resourceId: id,
        action,
      };
    }
  }

  const match = trimmed.match(MISSING_GRANT_RE);
  if (!match?.groups) return null;
  const { type, id, action } = match.groups;
  if (!type || !id || !action) return null;
  return {
    reason: trimmed,
    resourceType: type,
    resourceId: id,
    action,
  };
}

export function parseGatekeeperDenialFromOutput(
  output: string,
  toolName?: string,
): GatekeeperDenial | null {
  const inline = output.match(MISSING_GRANT_INLINE_RE);
  if (inline) {
    const parsed = parseMissingGrantReason(inline[0]);
    if (parsed) {
      return { toolName: toolName ?? 'tool', ...parsed };
    }
  }

  const match =
    output.match(GATEKEEPER_APPROVAL_RE) ?? output.match(GATEKEEPER_DENIAL_RE);
  if (!match?.groups?.reason) return null;
  const parsed = parseMissingGrantReason(match.groups.reason);
  if (!parsed) return null;
  return {
    toolName: toolName ?? 'tool',
    ...parsed,
  };
}

export function parseGatekeeperRequestPayload(
  payload: Record<string, unknown>,
): GatekeeperDenial | null {
  const tool = typeof payload.tool === 'string' ? payload.tool.trim() : '';
  const reason = typeof payload.reason === 'string' ? payload.reason.trim() : '';
  const resourceType =
    typeof payload.resource_type === 'string' ? payload.resource_type.trim() : '';
  const resourceId =
    typeof payload.resource_id === 'string' ? payload.resource_id.trim() : '';
  const action = typeof payload.action === 'string' ? payload.action.trim() : '';

  if (resourceType && resourceId && action) {
    return {
      toolName: tool || 'tool',
      reason: reason || `missing_grant:${resourceType}:${resourceId}:${action}`,
      resourceType,
      resourceId,
      action,
    };
  }

  if (reason) {
    const parsed = parseMissingGrantReason(reason);
    if (parsed) {
      return { toolName: tool || 'tool', ...parsed };
    }
  }

  return null;
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
