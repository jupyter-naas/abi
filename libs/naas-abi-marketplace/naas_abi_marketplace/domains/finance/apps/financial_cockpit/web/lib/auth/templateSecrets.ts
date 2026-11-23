/**
 * Values the template ships or documents for its secrets. A production
 * deployment that still holds one gets no sign-in and no sessions: it needs
 * secrets of its own (`npm run kickstart` generates both locally; set them with
 * `wrangler secret put` for a Worker).
 *
 * No imports: the module runs as is under node, for its tests.
 */
export const TEMPLATE_VALUES: readonly string[] = [
  'demo',
  'change-me-to-a-long-random-string',
];

/** The shortest session secret production accepts. */
export const MIN_SESSION_SECRET_LENGTH = 32;

export function isTemplateValue(value: string | undefined | null): boolean {
  const v = (value ?? '').trim();
  return TEMPLATE_VALUES.includes(v) || v.startsWith('change-me');
}

/**
 * The configured secret, or null when it is unset or, in production, a template
 * value or shorter than `minLength`.
 */
export function configuredSecret(
  value: string | undefined | null,
  { nodeEnv = process.env.NODE_ENV, minLength = 1 }: { nodeEnv?: string; minLength?: number } = {},
): string | null {
  const v = (value ?? '').trim();
  if (!v) return null;
  if (nodeEnv === 'production' && (isTemplateValue(v) || v.length < minLength)) {
    return null;
  }
  return v;
}
