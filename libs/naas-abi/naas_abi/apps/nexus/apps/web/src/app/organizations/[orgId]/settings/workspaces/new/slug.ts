/** Workspace slugs as the API accepts them: ^[a-z0-9][a-z0-9-]*[a-z0-9]$, max 100. */
export const WORKSPACE_SLUG = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

export function slugify(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100)
    .replace(/-+$/g, '');
}
