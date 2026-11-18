/**
 * Platform Settings › Organizations: the pure part (the table's columns, search and
 * sort, slugs, the delete confirmation, the API's words for a refusal).
 */

/** Platform Settings › Organizations (no React: the middleware reads it too). */
export const PLATFORM_ORGANIZATIONS_PATH = '/settings/organizations';

/** The page that creates one, with its general information. */
export const NEW_ORGANIZATION_PATH = `${PLATFORM_ORGANIZATIONS_PATH}/new`;

export interface PlatformOrganization {
  id: string;
  name: string;
  slug: string;
  legal_name?: string | null;
  website?: string | null;
  city?: string | null;
  country?: string | null;
  created_at?: string | null;
}

export type OrganizationColumnId = 'name' | 'id' | 'legal_name' | 'location' | 'website' | 'created';

export const ORGANIZATION_COLUMNS: { id: OrganizationColumnId; label: string }[] = [
  { id: 'name', label: 'Organization' },
  { id: 'id', label: 'ID' },
  { id: 'legal_name', label: 'Legal name' },
  { id: 'location', label: 'Location' },
  { id: 'website', label: 'Website' },
  { id: 'created', label: 'Created' },
];

/** "Paris, France", what is known of it, or "". */
export function organizationLocation(org: Pick<PlatformOrganization, 'city' | 'country'>): string {
  return [org.city, org.country].map((part) => part?.trim()).filter(Boolean).join(', ');
}

/** The website without its scheme and trailing slash: "acme.com". */
export function websiteLabel(website: string | null | undefined): string {
  return (website ?? '').trim().replace(/^https?:\/\//i, '').replace(/\/+$/, '');
}

/** The day it was created, YYYY-MM-DD, or "". */
export function createdDay(org: Pick<PlatformOrganization, 'created_at'>): string {
  return org.created_at ? org.created_at.slice(0, 10) : '';
}

/** A column's value as text, for sorting. */
export function columnText(org: PlatformOrganization, column: OrganizationColumnId): string {
  switch (column) {
    case 'name':
      return org.name;
    case 'id':
      return org.id;
    case 'legal_name':
      return org.legal_name ?? '';
    case 'location':
      return organizationLocation(org);
    case 'website':
      return websiteLabel(org.website);
    case 'created':
      return createdDay(org);
  }
}

/** Whether every word of the search is in the name, slug, id, legal name, place or website. */
export function matchesOrganization(org: PlatformOrganization, search: string): boolean {
  const words = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const text = [org.name, org.slug, org.id, org.legal_name, organizationLocation(org), websiteLabel(org.website)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return words.every((word) => text.includes(word));
}

/** Sorted by a column, blanks last whichever the direction, then by name. */
export function sortOrganizationsBy(
  found: PlatformOrganization[],
  column: OrganizationColumnId,
  direction: 'asc' | 'desc'
): PlatformOrganization[] {
  const sign = direction === 'asc' ? 1 : -1;
  return [...found].sort((a, b) => {
    const left = columnText(a, column);
    const right = columnText(b, column);
    if (!left !== !right) return left ? -1 : 1;
    return sign * left.localeCompare(right) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
  });
}

/** "1 organization", "3 organizations". */
export function organizationCount(n: number): string {
  return `${n} ${n === 1 ? 'organization' : 'organizations'}`;
}

/** A slug suggested from a name: lowercase ASCII words joined by dashes. */
export function slugFromName(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 63);
}

/** Delete is sent only once the organization's name is typed back exactly. */
export function deleteConfirmed(organization: PlatformOrganization, typed: string): boolean {
  return typed.trim() === organization.name.trim() && organization.name.trim() !== '';
}

/** What the API said about a refusal: its `detail` when it is text, else the status. */
export function errorText(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === 'string') return first.msg;
  }
  if (status === 403) return 'You may not do this.';
  if (status === 404) return 'Organization not found.';
  if (status === 0) return 'The API did not answer.';
  return `The API answered ${status}.`;
}

/** The organizations sorted by name, then id. */
export function sortOrganizations(found: PlatformOrganization[]): PlatformOrganization[] {
  return [...found].sort(
    (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id)
  );
}
