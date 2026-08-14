import {
  createApi,
  formatPublishedAt,
  loadEntitiesRegistry,
  loadLatestPublishedAt,
} from "../lib/api.js";
import { APP_NAME, BANNER_ICONS, PAGES } from "../lib/pages.js";
import { mountPageFor } from "../lib/registry.js";
import {
  buildPageUrl,
  migrateLegacyUrls,
  routeFromUrl,
  syncPageUrl,
  urlHasEntitySegment,
} from "../lib/routes.js";

const DEFAULT_ENTITY_ID = "demo";
const DEFAULT_ENTITY_SLUG = "demo";
const ORG_KEY = "cockpit-org-filter";
const RAIL_KEY = "cockpit-rail-collapsed";
const PAGE_KEY = "cockpit-page";
const BANNER_DISMISS_KEY = "cockpit-banner-dismissed";

const DEFAULT_ENTITY = {
  entity_id: DEFAULT_ENTITY_ID,
  url_slug: DEFAULT_ENTITY_SLUG,
  display_name: "Naas.ai",
  entity_type: "organization",
};

let currentEntity = DEFAULT_ENTITY_ID;
let currentEntitySlug = DEFAULT_ENTITY_SLUG;
let currentPageId = "workforce";
let entities = [];
let api = createApi(currentEntity);
const pageDisposers = {};

function defaultEntity() {
  return (
    entities.find((entity) => entity.entity_type === "organization") ||
    entities[0] ||
    DEFAULT_ENTITY
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
  if (!select) return;
  if ([...select.options].some((option) => option.value === currentEntitySlug)) {
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
  const map = dismissedBanners();
  map[pageId] = true;
  sessionStorage.setItem(BANNER_DISMISS_KEY, JSON.stringify(map));
  const el = document.getElementById("page-banner");
  el.hidden = true;
  el.dataset.page = "";
}

function showPageBanner(pageId) {
  const el = document.getElementById("page-banner");
  const cfg = PAGES[pageId]?.banner;
  if (!cfg?.enabled || !cfg.text?.trim() || dismissedBanners()[pageId]) {
    el.hidden = true;
    el.dataset.page = "";
    return;
  }
  const type = ["info", "warning", "error"].includes(cfg.type) ? cfg.type : "info";
  el.hidden = false;
  el.dataset.page = pageId;
  el.dataset.type = type;
  el.className = `page-banner type-${type}`;
  el.title = "Click to dismiss";
  document.getElementById("page-banner-text").textContent = cfg.text;
  document.getElementById("page-banner-icon").innerHTML =
    `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="${BANNER_ICONS[type]}" /></svg>`;
}

async function mountOrgFilter() {
  const select = document.getElementById("org-filter");
  if (!select) return;
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
    syncPageUrl(currentPageId, currentEntitySlug);
    showPage(currentPageId, { syncUrl: false });
  });
}

async function mountRailPublished() {
  const el = document.getElementById("rail-published");
  if (!el) return;
  try {
    const publishedAt = await loadLatestPublishedAt(api.loadJson);
    el.textContent = publishedAt
      ? `Published ${formatPublishedAt(publishedAt)}`
      : "Publication time unavailable";
  } catch {
    el.textContent = "Publication time unavailable";
  }
}

function resolveStoredPageId() {
  const stored = localStorage.getItem(PAGE_KEY);
  if (stored && PAGES[stored]) return stored;
  return "workforce";
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
  if (!PAGES[pageId]) pageId = "workforce";
  currentPageId = pageId;
  localStorage.setItem(PAGE_KEY, pageId);
  if (syncUrl) syncPageUrl(pageId, currentEntitySlug, { replace: replaceUrl });
  disposeOtherPages(pageId);
  document.querySelectorAll("#nav button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === pageId);
  });
  document.querySelectorAll(".page").forEach((p) => {
    p.classList.toggle("active", p.id === `page-${pageId}`);
  });
  const title = PAGES[pageId].title;
  document.getElementById("topbar-title").textContent = title;
  document.title = `${title} | ${APP_NAME}`;
  showPageBanner(pageId);
  const el = document.getElementById(`page-${pageId}`);
  el.innerHTML = `<p style="color:var(--muted)">Loading…</p>`;
  try {
    if (pageDisposers[pageId]) {
      pageDisposers[pageId]();
      delete pageDisposers[pageId];
    }
    const dispose = await mountPageFor(pageId, el, api);
    if (typeof dispose === "function") pageDisposers[pageId] = dispose;
  } catch (err) {
    el.innerHTML = `<p class="load-error">Failed to load data: ${err.message}. Run <code>make demo-data</code> in <code>domains/personnel</code> first.</p>`;
  }
}

document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-page]");
  if (!btn) return;
  e.stopPropagation();
  showPage(btn.dataset.page);
});

document.getElementById("rail-toggle").addEventListener("click", (e) => {
  e.stopPropagation();
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

window.addEventListener("popstate", handleUrlNavigation);

async function bootstrap() {
  setRailCollapsed(localStorage.getItem(RAIL_KEY) === "1");
  const { loadGlobal } = createApi(DEFAULT_ENTITY_ID);
  entities = await loadEntitiesRegistry(loadGlobal, DEFAULT_ENTITY);

  const route = routeFromUrl(routeContext());
  if (urlHasEntitySegment(routeContext())) {
    applyEntity(entityBySlug(route.entitySlug) || defaultEntity());
  } else {
    const storedEntityId = localStorage.getItem(ORG_KEY);
    const storedEntity = entities.find((entity) => entity.entity_id === storedEntityId);
    applyEntity(storedEntity || defaultEntity());
  }

  await mountOrgFilter();
  mountRailPublished();

  const migrated = migrateLegacyUrls({
    currentEntitySlug,
    defaultEntity,
  });
  const initialRoute = migrated || routeFromUrl(routeContext());
  applyEntity(entityBySlug(initialRoute.entitySlug) || defaultEntity());
  syncOrgSelect();
  showPage(initialRoute.pageId || resolveStoredPageId(), { replaceUrl: true });
}

bootstrap();
