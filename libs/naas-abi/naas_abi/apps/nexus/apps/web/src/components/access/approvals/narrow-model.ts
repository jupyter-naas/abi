/**
 * Narrowing a module's permission manifest before approving it. An approval may only
 * remove: an Allow statement loses actions and resources, never gains any, and a Deny
 * statement stays as submitted. Everything here is pure; the view only holds a `Choice`.
 */
import type { PolicyDocument, PolicyStatement } from '@/lib/iam-admin/types';

/** What stays, per statement of the submitted document (same order). A Deny entry is
 *  ignored: it always stays whole. */
export type Choice = { actions: Set<string>; resources: Set<string> }[];

export function initialChoice(document: PolicyDocument): Choice {
  return document.statements.map((s) => ({ actions: new Set(s.actions), resources: new Set(s.resources) }));
}

function flip(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export function toggleAction(choice: Choice, index: number, action: string): Choice {
  return choice.map((c, i) => (i === index ? { ...c, actions: flip(c.actions, action) } : c));
}

export function toggleResource(choice: Choice, index: number, resource: string): Choice {
  return choice.map((c, i) => (i === index ? { ...c, resources: flip(c.resources, resource) } : c));
}

/** An Allow statement that keeps at least one action and one resource stays. */
function survives(statement: PolicyStatement, kept: Choice[number]): boolean {
  return statement.effect === 'Deny' || (kept.actions.size > 0 && kept.resources.size > 0);
}

/** The document the selections describe: submitted order kept, the unselected removed. */
export function narrowed(document: PolicyDocument, choice: Choice): PolicyDocument {
  const statements: PolicyStatement[] = [];
  document.statements.forEach((statement, index) => {
    const kept = choice[index];
    if (statement.effect === 'Deny') {
      statements.push(statement);
    } else if (survives(statement, kept)) {
      statements.push({
        ...statement,
        actions: statement.actions.filter((a) => kept.actions.has(a)),
        resources: statement.resources.filter((r) => kept.resources.has(r)),
      });
    }
  });
  return { ...document, statements };
}

/** Nothing was removed: approving is then the plain approval, no document sent. */
export function isUnchanged(document: PolicyDocument, choice: Choice): boolean {
  return document.statements.every((statement, index) => {
    if (statement.effect === 'Deny') return true;
    const kept = choice[index];
    return kept.actions.size === statement.actions.length && kept.resources.size === statement.resources.length;
  });
}

export type NarrowSummary = {
  actionsRemoved: number;
  actionsTotal: number;
  resourcesRemoved: number;
  resourcesTotal: number;
  statementsDropped: number;
};

export function summarize(document: PolicyDocument, choice: Choice): NarrowSummary {
  const summary: NarrowSummary = {
    actionsRemoved: 0,
    actionsTotal: 0,
    resourcesRemoved: 0,
    resourcesTotal: 0,
    statementsDropped: 0,
  };
  document.statements.forEach((statement, index) => {
    if (statement.effect === 'Deny') return;
    const kept = choice[index];
    summary.actionsTotal += statement.actions.length;
    summary.resourcesTotal += statement.resources.length;
    summary.actionsRemoved += statement.actions.length - kept.actions.size;
    summary.resourcesRemoved += statement.resources.length - kept.resources.size;
    if (!survives(statement, kept)) summary.statementsDropped += 1;
  });
  return summary;
}

export function summaryText(summary: NarrowSummary): string {
  if (summary.actionsRemoved === 0 && summary.resourcesRemoved === 0) return 'Approved as submitted.';
  const parts = [
    `${summary.actionsRemoved} of ${summary.actionsTotal} actions removed`,
    `${summary.resourcesRemoved} of ${summary.resourcesTotal} resources removed`,
  ];
  if (summary.statementsDropped > 0) {
    parts.push(`${summary.statementsDropped} statement${summary.statementsDropped === 1 ? '' : 's'} dropped`);
  }
  return parts.join(', ');
}

/** Why this selection cannot be approved, or null. */
export function problem(document: PolicyDocument, choice: Choice): string | null {
  const allows = document.statements.filter((s) => s.effect === 'Allow');
  if (allows.length === 0) return null;
  const remaining = narrowed(document, choice).statements.filter((s) => s.effect === 'Allow');
  if (remaining.length === 0) return 'Nothing would be granted: reject the manifest instead.';
  return null;
}
