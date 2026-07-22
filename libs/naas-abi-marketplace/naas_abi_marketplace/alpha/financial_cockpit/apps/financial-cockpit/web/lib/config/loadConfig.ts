import 'server-only';

import yaml from 'js-yaml';

import rawConfig from '@/config/config.yaml';

import type {
  AppConfig,
  CompanyConfig,
  EntityConfig,
  EntityId,
  EntityType,
  NavSection,
  PageBannerConfig,
  PageId,
  SiteConfig,
  UserConfig,
} from '@/lib/types';
import { isPageId } from '@/lib/types';
import { loadEntitiesRegistry } from '@/lib/data/entitiesRegistry';

let cachedConfig: AppConfig | null = null;

// config.yaml holds only app + users/permissions — access control that lives
// with the code. Entities are generated data and load from the datastore
// (see getEntities), so they are intentionally absent here.
export function loadConfig(): AppConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  cachedConfig = yaml.load(rawConfig) as AppConfig;
  return cachedConfig;
}

export function getAppConfig() {
  return loadConfig().app;
}

export async function getEntities(): Promise<EntityConfig[]> {
  return loadEntitiesRegistry();
}

export async function getEntity(slug: string): Promise<EntityConfig | undefined> {
  return (await getEntities()).find((entity) => entity.url_slug === slug);
}

export async function getEntityById(
  entityId: EntityId,
): Promise<EntityConfig | undefined> {
  return (await getEntities()).find((entity) => entity.entity_id === entityId);
}

/**
 * Config.yaml admins only. For the full allowlist (admins + datastore users),
 * use `getUserById` / `getUserByEmail` from `@/lib/server/financeUsers`.
 */
export function getConfigUser(userId: string): UserConfig | undefined {
  return loadConfig().users.find((user) => user.user_id === userId);
}

/** @deprecated Prefer async financeUsers.getUserById — config admins only. */
export function getUser(userId: string): UserConfig | undefined {
  return getConfigUser(userId);
}

/** @deprecated Prefer async financeUsers.getUserByEmail — config admins only. */
export function getUserByEmail(email: string): UserConfig | undefined {
  const normalized = email.trim().toLowerCase();
  return loadConfig().users.find(
    (user) => user.email.toLowerCase() === normalized,
  );
}

/** Config.yaml users (admins). Prefer financeUsers.getAllUsers for the full list. */
export function getUsers(): UserConfig[] {
  return loadConfig().users;
}

export function isPageEnabled(pageId: PageId): boolean {
  const page = loadConfig().app.pages.find((entry) => entry.page_id === pageId);
  return page?.enabled ?? false;
}

/** @deprecated Use isPageEnabled */
export const isSectionEnabled = isPageEnabled;

export function getPageLabel(pageId: PageId): string {
  const page = loadConfig().app.pages.find((entry) => entry.page_id === pageId);
  return page?.label ?? pageId;
}

/** The page's banner when configured and enabled, otherwise null. */
export function getPageBanner(pageId: PageId): PageBannerConfig | null {
  const page = loadConfig().app.pages.find((entry) => entry.page_id === pageId);
  const banner = page?.banner;
  if (!banner || !banner.enabled || !banner.text?.trim()) {
    return null;
  }
  return { type: banner.type, text: banner.text, enabled: true };
}

/** @deprecated Use getPageLabel */
export const getSectionLabel = getPageLabel;

export function getEnabledPages(): PageId[] {
  return loadConfig()
    .app.pages.filter((entry) => entry.enabled && isPageId(entry.page_id))
    .map((entry) => entry.page_id);
}

/** @deprecated Use getEnabledPages */
export const getEnabledSections = getEnabledPages;

export function getNavSections(): NavSection[] {
  return loadConfig().app.sections.map((section) => ({
    id: section.section_id,
    label: section.label,
    pageIds: section.page_ids.filter((pageId): pageId is PageId => isPageId(pageId)),
  }));
}

export function navSectionForPage(pageId: PageId): NavSection | null {
  return getNavSections().find((section) => section.pageIds.includes(pageId)) ?? null;
}

export function isAdmin(user: UserConfig | SessionUser): boolean {
  return user.role === 'admin';
}

export type SessionUser = {
  userId: string;
  displayName: string;
  role?: 'admin';
  allowedEntities: EntityId[];
  allowedPages: PageId[];
};

export function canAccess(
  user: SessionUser,
  entityId: EntityId,
  pageId: PageId,
): boolean {
  if (!isPageEnabled(pageId)) {
    return false;
  }

  if (pageId === 'theme') {
    return false;
  }

  if (isAdmin(user)) {
    return true;
  }

  return (
    user.allowedEntities.includes(entityId) && user.allowedPages.includes(pageId)
  );
}

/** Theme is admin-only (managed from /admin). */
export function canAccessThemePage(user: SessionUser): boolean {
  if (!isPageEnabled('theme')) {
    return false;
  }

  return isAdmin(user);
}

export async function getAllowedEntities(
  user: SessionUser,
): Promise<EntityConfig[]> {
  const entities = await getEntities();
  if (isAdmin(user)) {
    return entities;
  }

  return entities.filter((entity) =>
    user.allowedEntities.includes(entity.entity_id),
  );
}

export function getAllowedPages(
  user: SessionUser,
  entityId?: EntityId,
): PageId[] {
  const enabled = getEnabledPages();

  if (isAdmin(user)) {
    return enabled;
  }

  const pages = user.allowedPages.filter((page) => enabled.includes(page));

  if (!entityId) {
    return pages;
  }

  if (!user.allowedEntities.includes(entityId)) {
    return [];
  }

  return pages;
}

export function getSite(
  entity: EntityConfig,
  siteSlug: string,
): SiteConfig | undefined {
  return entity.sites?.find((site) => site.site_id === siteSlug);
}

export function getEntityType(entity: EntityConfig): EntityType {
  return entity.entity_type ?? 'organization';
}

export function isConsolidation(entity: EntityConfig): boolean {
  return getEntityType(entity) === 'consolidation';
}

export function getConsolidationCompanies(entity: EntityConfig): CompanyConfig[] {
  return entity.companies ?? [];
}

export function getCompany(
  entity: EntityConfig,
  companySlug: string,
): CompanyConfig | undefined {
  return getConsolidationCompanies(entity).find(
    (company) => company.organization_slug === companySlug,
  );
}

export function resolveEntityEntryPath(
  user: SessionUser,
  entity: EntityConfig,
): string | null {
  const defaultPage = getAppConfig().default_page;
  const entityPages = getAllowedPages(user, entity.entity_id).filter(
    (pageId) => pageId !== 'theme',
  );
  const pageId =
    defaultPage !== 'theme' && entityPages.includes(defaultPage)
      ? defaultPage
      : entityPages[0];

  if (!pageId || !canAccess(user, entity.entity_id, pageId)) {
    return null;
  }

  return `/${entity.url_slug}/${pageId}`;
}

export async function resolveDefaultLanding(
  user: SessionUser,
): Promise<{ entitySlug: string; pageId: PageId } | null> {
  const entities = await getAllowedEntities(user);
  if (entities.length === 0) {
    return null;
  }

  const firstEntity = entities[0];
  const path = resolveEntityEntryPath(user, firstEntity);
  if (!path) {
    return null;
  }

  const pageId = path.split('/').pop() as PageId;
  return { entitySlug: firstEntity.url_slug, pageId };
}
