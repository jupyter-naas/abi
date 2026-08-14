import { PAGES } from "./pages.js";

export function graphSearchFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const next = new URLSearchParams();
  if (params.has("person")) next.set("person", params.get("person"));
  if (params.has("distance")) next.set("distance", params.get("distance"));
  const qs = next.toString();
  return qs ? `?${qs}` : "";
}

export function buildPageUrl(entitySlug, pageId) {
  const path = `/${encodeURIComponent(entitySlug)}/${encodeURIComponent(pageId)}`;
  const search = pageId === "graph" ? graphSearchFromLocation() : "";
  return `${path}${search}`;
}

/**
 * @param {{ entities: object[], resolveStoredPageId: () => string, defaultEntity: () => object, entityBySlug: (slug: string) => object | null }} ctx
 */
export function routeFromUrl(ctx) {
  const { resolveStoredPageId, defaultEntity, entityBySlug } = ctx;
  const segments = window.location.pathname.split("/").filter(Boolean);
  if (segments.length >= 2 && PAGES[segments[1]]) {
    return {
      entitySlug: decodeURIComponent(segments[0]),
      pageId: decodeURIComponent(segments[1]),
    };
  }
  if (segments.length === 1 && PAGES[segments[0]]) {
    return {
      entitySlug: defaultEntity().url_slug,
      pageId: decodeURIComponent(segments[0]),
    };
  }
  if (segments.length === 1) {
    const entity = entityBySlug(decodeURIComponent(segments[0]));
    if (entity) {
      return {
        entitySlug: entity.url_slug,
        pageId: resolveStoredPageId(),
      };
    }
  }
  return {
    entitySlug: defaultEntity().url_slug,
    pageId: null,
  };
}

/**
 * @param {{ currentEntitySlug: string, defaultEntity: () => object, buildPageUrl?: typeof buildPageUrl }} ctx
 */
export function migrateLegacyUrls(ctx) {
  const { currentEntitySlug, defaultEntity } = ctx;
  const hashMatch = /^#\/([^/?#]+)/.exec(window.location.hash);
  if (hashMatch) {
    const pageId = decodeURIComponent(hashMatch[1]);
    if (PAGES[pageId]) {
      const entitySlug = currentEntitySlug || defaultEntity().url_slug;
      window.history.replaceState(
        { pageId, entitySlug },
        "",
        buildPageUrl(entitySlug, pageId)
      );
      return { entitySlug, pageId };
    }
  }

  const segments = window.location.pathname.split("/").filter(Boolean);
  if (segments.length === 1 && PAGES[segments[0]]) {
    const pageId = decodeURIComponent(segments[0]);
    const entitySlug = currentEntitySlug || defaultEntity().url_slug;
    window.history.replaceState(
      { pageId, entitySlug },
      "",
      buildPageUrl(entitySlug, pageId)
    );
    return { entitySlug, pageId };
  }

  return null;
}

export function syncPageUrl(pageId, entitySlug, { replace = false } = {}) {
  const url = buildPageUrl(entitySlug, pageId);
  if (`${window.location.pathname}${window.location.search}` === url) return;
  window.history[replace ? "replaceState" : "pushState"](
    { pageId, entitySlug },
    "",
    url
  );
}

export function urlHasEntitySegment(ctx) {
  const segments = window.location.pathname.split("/").filter(Boolean);
  return (
    segments.length >= 2 ||
    (segments.length === 1 &&
      !PAGES[segments[0]] &&
      ctx.entityBySlug(decodeURIComponent(segments[0])))
  );
}
