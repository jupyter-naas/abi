import 'server-only';

/**
 * Perimeter scoping for entity-scoped API routes.
 *
 * The datastore keeps P&L adjustments, budget rows and invoice follow-up events
 * in *global* files — deliberately, so an edit made on a consolidation view is
 * visible from the organization view and vice versa. That design means the
 * `canAccess(session, entity, page)` check on a route only proves the caller may
 * see *this* perimeter; it says nothing about the rows the handler then reads or
 * writes. Every such handler must additionally constrain rows to the slugs the
 * current view actually covers — `perimeterSlugsFor(entity, company)`.
 *
 * Helpers here are the single place that constraint is expressed.
 */

/**
 * Slugs and record ids are used to build datastore paths (see invoicePdf.ts),
 * so they must never contain path separators or `..`. Anchored, no dots.
 */
const SAFE_SLUG_RE = /^[A-Za-z0-9_-]+$/;

export function isSafeSlug(value: string): boolean {
  return SAFE_SLUG_RE.test(value);
}

/**
 * True when `slug` is both well-formed and inside the current view's perimeter.
 * Callers should treat a false result as "not found" rather than "forbidden" so
 * the response does not confirm the existence of another tenant's perimeter.
 */
export function isSlugInPerimeter(
  slug: string,
  perimeterSlugs: ReadonlySet<string>,
): boolean {
  return isSafeSlug(slug) && perimeterSlugs.has(slug);
}

/** Filter records down to those whose `organization_slug` is in the perimeter. */
export function scopeToPerimeter<T extends { organization_slug: string }>(
  records: T[],
  perimeterSlugs: ReadonlySet<string>,
): T[] {
  return records.filter((record) => perimeterSlugs.has(record.organization_slug));
}
