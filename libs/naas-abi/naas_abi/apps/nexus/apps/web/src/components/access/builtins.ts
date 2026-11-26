/**
 * IAM's built-in policies as the Access pages show them (ADR `20261120_access_levels_and_groups`,
 * decision 7):
 * - "Platform member" and "Platform viewer" (`builtin.platform.member`, `.viewer`) are what IAM
 *   attaches with a workspace membership: shown on a person only as "Platform access (automatic)",
 *   never listed as a policy to attach, nor on the Policies list;
 * - the policies of IAM's own service accounts (Nexus API, Engine, Engine job, Built-in IdP,
 *   Module bootstrap) and each module's approved manifest (`module.<project>.<module>`, "Module
 *   <m>") appear only under Platform › Service accounts, read-only.
 */
import { isRoleCompanion } from './roles/role-change';

/** How a person's automatic platform policy reads, whichever of the two it is. */
export const PLATFORM_ACCESS_LABEL = 'Platform access (automatic)';

/** `builtin.platform.member` / `.viewer`: IAM's, with a workspace membership. */
export const isPlatformAccess = isRoleCompanion;

/** The built-in policies of IAM's own service accounts and jobs (core `roles.py`). */
export const SERVICE_ACCOUNT_POLICIES: readonly string[] = [
  'builtin.api',
  'builtin.engine',
  'builtin.job',
  'builtin.idp',
  'builtin.module_bootstrap',
];

/** A policy made for a service account: one of IAM's own accounts', or a module's approved
 *  manifest (`module.<project>.<module>`). */
export function isServiceAccountPolicy(policyId: string): boolean {
  return SERVICE_ACCOUNT_POLICIES.includes(policyId) || policyId.startsWith('module.');
}

/** Whether a policy is listed on a Policies page: neither the automatic platform access nor a
 *  service account's (Platform › Service accounts lists those). */
export function listedOnPolicies(policy: { id: string }): boolean {
  return !isPlatformAccess(policy.id) && !isServiceAccountPolicy(policy.id);
}
