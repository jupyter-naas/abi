export function graphSearchFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const next = new URLSearchParams();
  if (params.has("person")) next.set("person", params.get("person"));
  if (params.has("distance")) next.set("distance", params.get("distance"));
  const query = next.toString();
  return query ? `?${query}` : "";
}

export function buildPageUrl(entitySlug, page, pagesById) {
  const configured = pagesById[page] || page;
  const pageId = configured.page_id || page;
  const pageUrl = configured.url || page;
  const path = `/${encodeURIComponent(entitySlug)}/${encodeURIComponent(pageUrl)}`;
  return `${path}${pageId === "graph" ? graphSearchFromLocation() : ""}`;
}

export function routeFromUrl(ctx) {
  const { resolveStoredPageId, defaultEntity, entityBySlug, pagesByUrl } = ctx;
  const segments = window.location.pathname.split("/").filter(Boolean);
  const configured = pagesByUrl[decodeURIComponent(segments.at(-1) || "")];
  if (segments.length >= 2 && configured) {
    return {
      entitySlug: decodeURIComponent(segments[0]),
      pageId: configured.page_id,
    };
  }
  if (segments.length === 1 && configured) {
    return {
      entitySlug: defaultEntity().url_slug,
      pageId: configured.page_id,
    };
  }
  if (segments.length === 1) {
    const entity = entityBySlug(decodeURIComponent(segments[0]));
    if (entity) return { entitySlug: entity.url_slug, pageId: resolveStoredPageId() };
  }
  return { entitySlug: defaultEntity().url_slug, pageId: null };
}

export function migrateLegacyUrls(ctx) {
  const { currentEntitySlug, defaultEntity, pagesByUrl, pagesById } = ctx;
  const hashMatch = /^#\/([^/?#]+)/.exec(window.location.hash);
  const legacyUrl = hashMatch?.[1] || (
    window.location.pathname.split("/").filter(Boolean).length === 1
      ? window.location.pathname.split("/").filter(Boolean)[0]
      : null
  );
  const page = legacyUrl ? pagesByUrl[decodeURIComponent(legacyUrl)] : null;
  if (!page) return null;
  const entitySlug = currentEntitySlug || defaultEntity().url_slug;
  window.history.replaceState(
    { pageId: page.page_id, entitySlug },
    "",
    buildPageUrl(entitySlug, page.page_id, pagesById)
  );
  return { entitySlug, pageId: page.page_id };
}

export function syncPageUrl(
  pageId,
  entitySlug,
  pagesById,
  { replace = false } = {}
) {
  const url = buildPageUrl(entitySlug, pageId, pagesById);
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
      !ctx.pagesByUrl[decodeURIComponent(segments[0])] &&
      ctx.entityBySlug(decodeURIComponent(segments[0])))
  );
}
