/**
 * Compatibility exports for browser tabs that cached the pre-config shell.
 * New code reads config through config.js; remove this only after old clients
 * can no longer have the previous module graph cached.
 */
import { loadAppConfig } from "./config.js?v=2";

const config = await loadAppConfig();

export const PAGES = Object.fromEntries(
  config.app.pages.map((page) => [
    page.page_id,
    {
      title: page.label,
      banner: page.banner,
    },
  ])
);

export const PAGE_IDS = Object.freeze(Object.keys(PAGES));
export const APP_NAME = config.brand.name;
export const BANNER_ICONS = config.theme.banner_icons;
