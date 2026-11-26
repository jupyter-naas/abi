/**
 * Batched Settings reads (#1608): what a page needs of many groups or principals, in as few
 * requests as the API's bounds allow, never one per item. IAM authorizes each item inside
 * the batch exactly as it does the per-item read; nothing here decides access.
 */
import type { IamAdminApi } from './api';
import type { AttachmentView, GroupSummary } from './types';

/** The largest page of `GET /groups` (the API refuses more). */
export const GROUPS_PAGE_MAX = 500;
/** The principals one `GET /attachments` may name (the API refuses more). */
export const MAX_PRINCIPALS_PER_READ = 100;

/**
 * Every group of `scope` the caller may list, in the API's order, with each one's
 * `member_count` (null where the caller may not read the group): one request per page of
 * `GROUPS_PAGE_MAX`. A refusal is thrown, as the list's.
 */
export async function listAllGroups(api: IamAdminApi, scope?: string): Promise<GroupSummary[]> {
  const found: GroupSummary[] = [];
  const seen = new Set<string>();
  let after: string | null = null;
  for (;;) {
    const page = await api.listGroups(scope, { after, limit: GROUPS_PAGE_MAX, memberCounts: true });
    for (const group of page.items) {
      if (!seen.has(group.id)) {
        seen.add(group.id);
        found.push(group);
      }
    }
    const next = page.next_after ?? null;
    // A cursor that does not move would read the same page forever.
    if (next === null || next === after) return found;
    after = next;
  }
}

export type PrincipalAttachments = { items: AttachmentView[]; error?: Error };

/**
 * The attachments of each of `principalIds` (at `scope` when given, else at every level IAM
 * lets the caller list), by principal: one request per `MAX_PRINCIPALS_PER_READ`. A request
 * that fails leaves its principals with no rows and its error, so the page can say which.
 */
export async function attachmentsByPrincipal(
  api: IamAdminApi,
  principalIds: readonly string[],
  scope?: string | null,
): Promise<Map<string, PrincipalAttachments>> {
  const ids = [...new Set(principalIds)];
  const found = new Map<string, PrincipalAttachments>(ids.map((id) => [id, { items: [] }]));
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += MAX_PRINCIPALS_PER_READ) chunks.push(ids.slice(i, i + MAX_PRINCIPALS_PER_READ));
  await Promise.all(
    chunks.map(async (chunk) => {
      try {
        const page = await api.listAttachments(scope ? { principal_id: chunk, scope } : { principal_id: chunk });
        for (const attachment of page.items) found.get(attachment.principal_id)?.items.push(attachment);
      } catch (e) {
        const error = e instanceof Error ? e : new Error(String(e));
        for (const id of chunk) found.set(id, { items: [], error });
      }
    }),
  );
  return found;
}
