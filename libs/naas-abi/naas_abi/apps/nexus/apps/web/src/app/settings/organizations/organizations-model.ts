/**
 * Platform Settings › Organizations: the pure part (slugs, the delete
 * confirmation, the API's words for a refusal).
 */

/** Platform Settings › Organizations (no React: the middleware reads it too). */
export const PLATFORM_ORGANIZATIONS_PATH = '/settings/organizations';

export interface PlatformOrganization {
  id: string;
  name: string;
  slug: string;
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
