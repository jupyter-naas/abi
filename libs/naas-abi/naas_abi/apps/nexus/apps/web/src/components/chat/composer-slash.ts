/** Compact slash list for the chat composer: slug and short name. */

export type ComposerSlashSkill = {
  slug: string;
  name?: string;
  enabled: boolean;
  lastUsedAt?: string | null;
};

export type ComposerSlashSuggestion = {
  slug: string;
  name: string;
};

/** Active only for a slash token with no spaces: `/`, `/sl`, `/slides`. */
const SLASH_TOKEN = /^\/\S*$/;
const SLUG_QUERY = /^[a-z0-9_-]*$/;

const usedAt = (value: string | null): number => {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
};

const shortName = (slug: string, name: string | undefined): string => {
  const trimmed = name?.trim();
  return trimmed || slug;
};

/**
 * Enabled skills whose slug matches the token after `/`.
 * An empty composer, or any text that is not a slash token, yields nothing.
 * A bare `/` lists every enabled skill. `/sl` keeps prefix matches.
 * An exact slug stays in the list: a finished command is not dropped.
 * Descriptions stay in the plus menu.
 */
export function composerSlashSuggestions(
  input: string,
  skills: readonly ComposerSlashSkill[] | null,
): ComposerSlashSuggestion[] {
  if (!SLASH_TOKEN.test(input)) return [];
  const query = input.slice(1).toLowerCase();
  if (!SLUG_QUERY.test(query)) return [];

  const seen = new Set<string>();
  const enabled: { slug: string; name: string; lastUsedAt: string | null }[] = [];
  for (const skill of skills ?? []) {
    if (!skill.enabled) continue;
    const slug = skill.slug.trim();
    const key = slug.toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    enabled.push({
      slug,
      name: shortName(slug, skill.name),
      lastUsedAt: skill.lastUsedAt ?? null,
    });
  }

  const starts = enabled.filter((skill) => skill.slug.toLowerCase().startsWith(query));
  const pool =
    starts.length > 0
      ? starts
      : enabled.filter((skill) => skill.slug.toLowerCase().includes(query));

  pool.sort((a, b) => {
    const used = usedAt(b.lastUsedAt) - usedAt(a.lastUsedAt);
    if (used !== 0) return used;
    return a.slug.localeCompare(b.slug);
  });

  return pool.map(({ slug, name }) => ({ slug, name }));
}
