/** Workspace › General: the organization's colors among a workspace's color choices. */

/** The organization's primary and accent colors as color choices (none it leaves unset). */
export function organizationColors(org: { name?: string; primary_color?: string; accent_color?: string }) {
  const who = org.name?.trim() || 'Organization';
  const found = [
    { name: `${who} primary`, value: org.primary_color?.trim() ?? '' },
    { name: `${who} accent`, value: org.accent_color?.trim() ?? '' },
  ].filter((c) => /^#[0-9a-f]{3,8}$/i.test(c.value));
  return found.filter((c, i) => found.findIndex((o) => o.value.toLowerCase() === c.value.toLowerCase()) === i);
}
