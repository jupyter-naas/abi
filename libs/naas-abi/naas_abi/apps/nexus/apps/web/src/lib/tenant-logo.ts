/**
 * The tenant logo's default height. No React: Platform Settings › General
 * (`app/settings/general/general-model.ts`) reads it, and the Next.js
 * middleware imports that module.
 */

/** The logo image height when `tenant.logo_height` is unset (the former `h-12`), in pixels. */
export const DEFAULT_LOGO_HEIGHT = 48;
