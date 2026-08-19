import {
  createApi,
  formatPublishedAt,
  loadEntitiesRegistry,
  loadLatestPublishedAt,
} from "../lib/api.js";
import {
  applyBrand,
  applyTheme,
  loadAppConfig,
  pageMaps,
  renderConfiguredPages,
} from "../lib/config.js?v=2";
import { mountPageFor } from "../lib/registry.js?v=11";
import {
  migrateLegacyUrls,
  routeFromUrl,
  syncPageUrl,
  urlHasEntitySegment,
} from "../lib/routes.js?v=2";

const ORG_KEY = "cockpit-org-filter";
const RAIL_KEY = "cockpit-rail-collapsed";
const PAGE_KEY = "cockpit-page";
const BANNER_DISMISS_KEY = "cockpit-banner-dismissed";

let config;
let pages = [];
let pagesById = {};
let pagesByUrl = {};
let defaultEntityConfig;
let currentEntity;
let currentEntitySlug;
let currentPageId;
let entities = [];
let api;
const pageDisposers = {};

function defaultEntity() {
  const configured = entities.find(
    (entity) => entity.entity_id === defaultEntityConfig.entity_id
  );
  return (
    configured ||
    entities.find((entity) => entity.entity_type === "organization") ||
    entities[0] ||
    defaultEntityConfig
  );
}

function entityBySlug(slug) {
  return entities.find((entity) => entity.url_slug === slug) || null;
}

function routeContext() {
  return {
    entities,
    resolveStoredPageId,
    defaultEntity,
    entityBySlug,
    pagesById,
    pagesByUrl,
  };
}

function applyEntity(entity) {
  if (!entity) return;
  currentEntity = entity.entity_id;
  currentEntitySlug = entity.url_slug;
  api = createApi(currentEntity);
  localStorage.setItem(ORG_KEY, currentEntity);
}

function syncOrgSelect() {
  const select = document.getElementById("org-filter");
  if (
    select &&
    [...select.options].some((option) => option.value === currentEntitySlug)
  ) {
    select.value = currentEntitySlug;
  }
}

function setRailCollapsed(collapsed) {
  const shell = document.querySelector(".shell");
  const toggle = document.getElementById("rail-toggle");
  shell.classList.toggle("rail-collapsed", collapsed);
  toggle.hidden = collapsed;
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.setAttribute("aria-label", "Collapse sidebar");
  toggle.title = "Collapse sidebar";
  localStorage.setItem(RAIL_KEY, collapsed ? "1" : "0");
}

function dismissedBanners() {
  try {
    return JSON.parse(sessionStorage.getItem(BANNER_DISMISS_KEY) || "{}");
  } catch {
    return {};
  }
}

function dismissBanner(pageId) {
  const dismissed = dismissedBanners();
  dismissed[pageId] = true;
  sessionStorage.setItem(BANNER_DISMISS_KEY, JSON.stringify(dismissed));
  const element = document.getElementById("page-banner");
  element.hidden = true;
  element.dataset.page = "";
  syncBannerRestore(pageId);
}

function restoreBanner(pageId) {
  const dismissed = dismissedBanners();
  delete dismissed[pageId];
  sessionStorage.setItem(BANNER_DISMISS_KEY, JSON.stringify(dismissed));
  showPageBanner(pageId);
}

function syncBannerRestore(pageId) {
  const restore = document.getElementById("banner-restore");
  const banner = pagesById[pageId]?.banner;
  restore.dataset.type = ["info", "warning", "error"].includes(banner?.type)
    ? banner.type
    : "info";
  restore.hidden = !(
    banner?.enabled &&
    banner.text?.trim() &&
    dismissedBanners()[pageId]
  );
}

function showPageBanner(pageId) {
  const element = document.getElementById("page-banner");
  const banner = pagesById[pageId]?.banner;
  if (!banner?.enabled || !banner.text?.trim() || dismissedBanners()[pageId]) {
    element.hidden = true;
    element.dataset.page = "";
    syncBannerRestore(pageId);
    return;
  }
  const type = ["info", "warning", "error"].includes(banner.type)
    ? banner.type
    : "info";
  const icon = config.theme?.banner_icons?.[type] || "";
  element.hidden = false;
  element.dataset.page = pageId;
  element.dataset.type = type;
  element.className = `page-banner type-${type}`;
  element.title = "Click to dismiss";
  document.getElementById("page-banner-text").textContent = banner.text;
  document.getElementById("page-banner-icon").innerHTML =
    `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="${icon}" /></svg>`;
  syncBannerRestore(pageId);
}

async function mountOrgFilter() {
  const select = document.getElementById("org-filter");
  select.innerHTML = entities
    .map(
      (entity) =>
        `<option value="${entity.url_slug}">${entity.display_name || entity.organizationLabel || entity.url_slug}</option>`
    )
    .join("");
  syncOrgSelect();
  select.addEventListener("change", () => {
    const entity = entityBySlug(select.value);
    if (!entity) return;
    applyEntity(entity);
    syncPageUrl(currentPageId, currentEntitySlug, pagesById);
    showPage(currentPageId, { syncUrl: false });
  });
}

async function mountRailPublished() {
  const element = document.getElementById("rail-published");
  try {
    const publishedAt = await loadLatestPublishedAt(api.loadJson);
    element.textContent = publishedAt
      ? `Published ${formatPublishedAt(publishedAt)}`
      : "Publication time unavailable";
  } catch {
    element.textContent = "Publication time unavailable";
  }
}

function resolveStoredPageId() {
  const stored = localStorage.getItem(PAGE_KEY);
  return pagesById[stored] ? stored : config.app.default_page;
}

function disposeOtherPages(activePageId) {
  for (const [pageId, dispose] of Object.entries(pageDisposers)) {
    if (pageId !== activePageId && dispose) {
      dispose();
      delete pageDisposers[pageId];
    }
  }
}

async function showPage(pageId, { syncUrl = true, replaceUrl = false } = {}) {
  if (!pagesById[pageId]) pageId = config.app.default_page;
  currentPageId = pageId;
  localStorage.setItem(PAGE_KEY, pageId);
  if (syncUrl) {
    syncPageUrl(pageId, currentEntitySlug, pagesById, { replace: replaceUrl });
  }
  disposeOtherPages(pageId);
  document.querySelectorAll("#nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.page === pageId);
  });
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.toggle("active", page.id === `page-${pageId}`);
  });

  const title = pagesById[pageId].label;
  document.getElementById("topbar-title").textContent = title;
  document.title = `${title} | ${config.brand.name}`;
  showPageBanner(pageId);

  const element = document.getElementById(`page-${pageId}`);
  element.innerHTML = `<p style="color:var(--muted)">Loading…</p>`;
  try {
    if (pageDisposers[pageId]) pageDisposers[pageId]();
    const dispose = await mountPageFor(pageId, element, { ...api, config });
    if (typeof dispose === "function") pageDisposers[pageId] = dispose;
  } catch (error) {
    element.innerHTML = `<p class="load-error">Failed to load data: ${error.message}.</p>`;
  }
}

function handleUrlNavigation() {
  const route = routeFromUrl(routeContext());
  const entity = entityBySlug(route.entitySlug) || defaultEntity();
  const entityChanged = entity.entity_id !== currentEntity;
  if (entityChanged) {
    applyEntity(entity);
    syncOrgSelect();
  }
  const pageId = route.pageId || currentPageId;
  if (pageId !== currentPageId || entityChanged) {
    showPage(pageId, { syncUrl: false });
  }
}

async function bootstrap() {
  config = await loadAppConfig();
  ({ pages, byId: pagesById, byUrl: pagesByUrl } = pageMaps(config));
  defaultEntityConfig = config.app.default_entity;
  currentPageId = config.app.default_page;
  currentEntity = defaultEntityConfig.entity_id;
  currentEntitySlug = defaultEntityConfig.url_slug;
  api = createApi(currentEntity);

  applyTheme(config);
  applyBrand(config);
  renderConfiguredPages(config);
  setRailCollapsed(localStorage.getItem(RAIL_KEY) === "1");

  document.getElementById("nav").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-page]");
    if (!button) return;
    event.stopPropagation();
    showPage(button.dataset.page);
  });
  document.getElementById("rail-toggle").addEventListener("click", (event) => {
    event.stopPropagation();
    setRailCollapsed(true);
  });
  document.getElementById("rail").addEventListener("click", () => {
    if (document.querySelector(".shell").classList.contains("rail-collapsed")) {
      setRailCollapsed(false);
    }
  });
  document.getElementById("page-banner").addEventListener("click", () => {
    const pageId = document.getElementById("page-banner").dataset.page;
    if (pageId) dismissBanner(pageId);
  });
  const restore = document.getElementById("banner-restore");
  const restoreLabel = config.app.banner_restore_label;
  const restoreIcon = config.theme?.banner_icons?.restore || "";
  restore.title = restoreLabel;
  restore.setAttribute("aria-label", restoreLabel);
  restore.innerHTML =
    `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="${restoreIcon}" /></svg>`;
  restore.addEventListener("click", () => restoreBanner(currentPageId));
  window.addEventListener("popstate", handleUrlNavigation);

  const { loadGlobal } = createApi(defaultEntityConfig.entity_id);
  entities = await loadEntitiesRegistry(loadGlobal, defaultEntityConfig);
  const route = routeFromUrl(routeContext());
  if (urlHasEntitySegment(routeContext())) {
    applyEntity(entityBySlug(route.entitySlug) || defaultEntity());
  } else {
    const storedId = localStorage.getItem(ORG_KEY);
    applyEntity(
      entities.find((entity) => entity.entity_id === storedId) || defaultEntity()
    );
  }

  await mountOrgFilter();
  mountRailPublished();
  const migrated = migrateLegacyUrls({
    ...routeContext(),
    currentEntitySlug,
  });
  const initialRoute = migrated || routeFromUrl(routeContext());
  applyEntity(entityBySlug(initialRoute.entitySlug) || defaultEntity());
  syncOrgSelect();
  showPage(initialRoute.pageId || resolveStoredPageId(), { replaceUrl: true });
}

bootstrap().catch((error) => {
  document.getElementById("pages").innerHTML =
    `<p class="load-error">Failed to load cockpit configuration: ${error.message}</p>`;
});
