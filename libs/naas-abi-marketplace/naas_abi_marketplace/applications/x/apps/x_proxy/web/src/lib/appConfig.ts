/**
 * The app's navigation, as the components ask about it.
 *
 * `config.yaml` at the app root is the source of truth; `app_config.py` compiles
 * it into `appConfig.generated.ts`, and this module turns that data into the
 * lookups the chrome needs. Nothing here decides anything — change the YAML,
 * not this file.
 */
import {
  DEFAULT_PAGE,
  SECTIONS,
  type PageConfig,
  type PageKey,
  type SectionConfig,
  type SectionKey,
} from "@/lib/appConfig.generated";

export {
  APP_NAME,
  APP_TITLE,
  DEFAULT_PAGE,
  FAVORITES_LIMITS,
  FEED,
  SECTIONS,
} from "@/lib/appConfig.generated";
export type {
  IconName,
  PageConfig,
  PageKey,
  SectionConfig,
  SectionKey,
} from "@/lib/appConfig.generated";

import { APP_NAME, APP_TITLE } from "@/lib/appConfig.generated";

/** Every configured page, in config order, visible or not. */
export const PAGES: PageConfig[] = SECTIONS.flatMap((section) => section.pages);

const PAGE_BY_KEY = new Map(PAGES.map((page) => [page.key, page]));
const SECTION_BY_PAGE = new Map(
  SECTIONS.flatMap((section) =>
    section.pages.map((page) => [page.key, section] as const),
  ),
);
const SECTION_BY_KEY = new Map(
  SECTIONS.map((section) => [section.key, section] as const),
);

/**
 * Path of each page, relative to the app root.
 *
 * Next prepends `basePath` for `<Link>` hrefs, and the same-page writers in
 * `lib/routes.ts` never touch the path, so neither needs to know it.
 */
export const PAGE_PATHS = Object.fromEntries(
  PAGES.map((page) => [page.key, page.path]),
) as Record<PageKey, string>;

/** The generated union guarantees the key exists; the throw is for JS callers. */
export function pageConfig(page: PageKey): PageConfig {
  const found = PAGE_BY_KEY.get(page);
  if (!found) throw new Error(`Unknown page: ${page}`);
  return found;
}

export function sectionConfig(section: SectionKey): SectionConfig {
  const found = SECTION_BY_KEY.get(section);
  if (!found) throw new Error(`Unknown section: ${section}`);
  return found;
}

export function sectionOf(page: PageKey): SectionConfig {
  const found = SECTION_BY_PAGE.get(page);
  if (!found) throw new Error(`Page in no section: ${page}`);
  return found;
}

/** The section's tabs — hidden pages keep their route but leave the strip. */
export function tabsOf(section: SectionKey): PageConfig[] {
  return sectionConfig(section).pages.filter((page) => page.visible);
}

/** Rail entries of one group, in config order. */
export function railSections(place: SectionConfig["place"]): SectionConfig[] {
  return SECTIONS.filter(
    (section) => section.visible && section.place === place,
  );
}

/**
 * Where a section opens: its first visible page, or its first page when the
 * whole section is hidden from the rail but still reachable by URL.
 */
export function landingPageOf(section: SectionKey): PageKey {
  const pages = sectionConfig(section).pages;
  return (pages.find((page) => page.visible) || pages[0]).key;
}

/** `"X Proxy - Users"`, from `app.title` in the YAML. */
export function titleOf(section: SectionKey): string {
  return APP_TITLE.replace("{app}", APP_NAME).replace(
    "{section}",
    sectionConfig(section).label,
  );
}

/** Every section's landing page, keyed by section — the initial "last visited". */
export function landingPages(): Record<SectionKey, PageKey> {
  return Object.fromEntries(
    SECTIONS.map((section) => [section.key, landingPageOf(section.key)]),
  ) as Record<SectionKey, PageKey>;
}

/** Guard for `DEFAULT_PAGE` staying a real page after a config edit. */
export const DEFAULT_PAGE_PATH = PAGE_PATHS[DEFAULT_PAGE];
