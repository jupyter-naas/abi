import { describe, expect, it } from 'vitest';

import {
  parseGatekeeperDenialFromOutput,
  parseGatekeeperRequestPayload,
  parseMissingGrantReason,
} from './gatekeeper';

describe('gatekeeper parsing', () => {
  it('parses missing_grant reason tokens', () => {
    expect(
      parseMissingGrantReason('missing_grant:github.repo:acme/app:read_secrets'),
    ).toEqual({
      reason: 'missing_grant:github.repo:acme/app:read_secrets',
      resourceType: 'github.repo',
      resourceId: 'acme/app',
      action: 'read_secrets',
    });
  });

  it('parses approval-required tool output', () => {
    const output =
      'Gatekeeper approval required: missing_grant:github.repo:acme/app:read_secrets. Waiting for the user to approve access.';
    expect(parseGatekeeperDenialFromOutput(output, 'github_list_repo_secrets')).toEqual({
      toolName: 'github_list_repo_secrets',
      reason: 'missing_grant:github.repo:acme/app:read_secrets',
      resourceType: 'github.repo',
      resourceId: 'acme/app',
      action: 'read_secrets',
    });
  });

  it('parses legacy access-denied tool output', () => {
    const output =
      'Access denied by gatekeeper: missing_grant:github.repo:acme/app:delete_repo.';
    expect(parseGatekeeperDenialFromOutput(output, 'github_delete_organization_repository')).toEqual({
      toolName: 'github_delete_organization_repository',
      reason: 'missing_grant:github.repo:acme/app:delete_repo',
      resourceType: 'github.repo',
      resourceId: 'acme/app',
      action: 'delete_repo',
    });
  });

  it('parses gatekeeper_request SSE payload', () => {
    expect(
      parseGatekeeperRequestPayload({
        tool: 'github_list_repo_secrets',
        reason: 'missing_grant:github.repo:acme/app:read_secrets',
        resource_type: 'github.repo',
        resource_id: 'acme/app',
        action: 'read_secrets',
      }),
    ).toEqual({
      toolName: 'github_list_repo_secrets',
      reason: 'missing_grant:github.repo:acme/app:read_secrets',
      resourceType: 'github.repo',
      resourceId: 'acme/app',
      action: 'read_secrets',
    });
  });
});
