// Add people (Workspace settings › Members): the pure part of the search box. What the
// listbox offers for a text, which option the keyboard moves to, the roles a pick offers.

import { candidateLabel, candidateQuery, looksLikeEmail, type MemberCandidate, type WorkspaceRole } from '@/lib/people';

export type AddPeopleOption =
  | { kind: 'candidate'; key: string; candidate: MemberCandidate }
  | { kind: 'create'; key: string; text: string };

/** The answer a search gave, for the text it answers. */
export type FoundPeople = { text: string; items: MemberCandidate[] };

export type AddPeopleListing = {
  /** False while the text is too short, or its search has not answered yet. */
  ready: boolean;
  options: AddPeopleOption[];
  /** How many suggestions were left out because they already are members here. */
  excluded: number;
};

/**
 * What the listbox offers for `typed`: the suggestions of its own search (never an older
 * text's), minus anyone already a member here, then "Create user '<text>'" when nobody
 * matches, or when an email is typed that no suggestion has (someone of another organization
 * is added by their exact email).
 */
export function addPeopleListing(
  typed: string,
  found: FoundPeople,
  memberIds: ReadonlySet<string> = new Set()
): AddPeopleListing {
  const q = candidateQuery(typed);
  if (!q || found.text !== q) return { ready: false, options: [], excluded: 0 };
  const kept = found.items.filter((c) => !memberIds.has(c.user_id));
  const options: AddPeopleOption[] = kept.map((candidate) => ({
    kind: 'candidate',
    key: `candidate:${candidate.user_id}`,
    candidate,
  }));
  const exact = kept.some((c) => c.email.toLowerCase() === q.toLowerCase());
  if (kept.length === 0 || (looksLikeEmail(q) && !exact)) {
    options.push({ kind: 'create', key: 'create', text: q });
  }
  return { ready: true, options, excluded: found.items.length - kept.length };
}

/** The text of an option, as the listbox shows it. */
export function optionText(option: AddPeopleOption): string {
  return option.kind === 'create' ? `Create user '${option.text}'` : candidateLabel(option.candidate);
}

/**
 * The option the keyboard moves to, from `active` (-1: none) among `count`. Arrows wrap
 * around, Home and End go to the first and last; any other key leaves it.
 */
export function moveActive(active: number, key: string, count: number): number {
  if (count <= 0) return -1;
  switch (key) {
    case 'ArrowDown':
      return active < 0 || active >= count - 1 ? 0 : active + 1;
    case 'ArrowUp':
      return active <= 0 ? count - 1 : active - 1;
    case 'Home':
      return 0;
    case 'End':
      return count - 1;
    default:
      return Math.min(active, count - 1);
  }
}

/** The roles a pick offers: member, viewer, admin; owner only to an owner of the workspace. */
export function addableRoles(callerRole: string | null | undefined): WorkspaceRole[] {
  const roles: WorkspaceRole[] = ['member', 'viewer', 'admin'];
  return callerRole === 'owner' ? [...roles, 'owner'] : roles;
}
