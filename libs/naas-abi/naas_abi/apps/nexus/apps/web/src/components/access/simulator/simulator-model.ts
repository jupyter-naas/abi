import type { DecidingStatement, Simulation } from '@/lib/iam-admin/types';
import { scopeLabel } from '../attachments/attachments-model';

/** IAM's reason for a decision, in a sentence. */
export function reasonText(reason: string): string {
  switch (reason) {
    case 'allow':
      return 'A statement allows it and no Deny excludes it.';
    case 'explicit_deny':
      return 'A Deny statement matches: an explicit Deny always wins.';
    case 'implicit_deny':
      return 'No statement allows it: everything is denied unless a policy allows it.';
    case 'suspended':
      return 'The principal is suspended or deleted: it is denied everything.';
    case 'sealed':
      return 'The resource is sealed: only its owner opens it, whatever the policies say.';
    default:
      return reason;
  }
}

export function headline(simulation: Pick<Simulation, 'allowed'>): string {
  return simulation.allowed ? 'Allowed' : 'Denied';
}

/** Whose statement decided: a call can be the principal's own, its user's, or a token's. */
export function sideText(side: DecidingStatement['side']): string {
  switch (side) {
    case 'actor':
      return 'the principal itself';
    case 'user':
      return 'the user it acts for';
    case 'token':
      return 'the scope of its token';
  }
}

export type Fact = { label: string; value: string };

/** What to show of the deciding statement, in reading order; empty fields are left out. */
export function statementFacts(statement: DecidingStatement): Fact[] {
  const facts: Fact[] = [
    { label: 'Effect', value: statement.effect },
    { label: 'Held by', value: sideText(statement.side) },
    {
      label: 'Policy',
      value: statement.policy_name
        ? `${statement.policy_name} (${statement.policy_id})`
        : (statement.policy_id ?? 'the token'),
    },
    {
      label: 'Statement',
      value: `#${statement.statement_index + 1}${statement.sid ? ` (${statement.sid})` : ''}`,
    },
  ];
  if (statement.attachment_id) facts.push({ label: 'Attachment', value: statement.attachment_id });
  if (statement.scope) facts.push({ label: 'Attached at', value: scopeLabel(statement.scope) });
  if (statement.via_group) facts.push({ label: 'Through group', value: statement.via_group });
  return facts;
}
