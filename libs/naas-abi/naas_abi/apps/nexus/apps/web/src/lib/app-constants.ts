/** Module categories that represent launchable web applications. */
export const APP_CATEGORIES = new Set(['application', 'alpha']);

export function hasApp(mod: { category: string; app_url?: string | null }): boolean {
  return APP_CATEGORIES.has(mod.category) || !!mod.app_url;
}
