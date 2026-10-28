/**
 * Hash routing.
 *
 * The app is served both by its dev server and, inside Nexus, from
 * /app-html/<module>/people/. A hash route is the only one that survives both
 * without knowing its own base path.
 */

function defaultPageId(config) {
  return config.app?.default_page || "home";
}

export function parseRoute(config) {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, queryString] = raw.split("?");
  const params = new URLSearchParams(queryString || "");
  const segments = path.split("/").filter(Boolean);
  const pages = config.app?.pages || [];
  const byUrl = Object.fromEntries(pages.map((page) => [page.url, page.page_id]));

  if (!segments.length) return { pageId: defaultPageId(config), params };
  const pageId = byUrl[segments[0]];
  if (pageId === "profile") {
    return { pageId: "profile", slug: decodeURIComponent(segments[1] || ""), params };
  }
  if (pageId) return { pageId, params };
  return { pageId: "home", params };
}

/** Canonical hash when the location bar is empty (respects default page and results tab). */
export function landingHref(config) {
  const pageId = defaultPageId(config);
  if (pageId === "home") return "#/";
  const page = (config.app?.pages || []).find((item) => item.page_id === pageId);
  if (!page) return "#/";
  if (pageId === "results") {
    // default_results_view "network" is the People tab drawn as a network.
    return searchHref(config, { display: config.app?.default_results_view || "" });
  }
  return `#/${page.url}`;
}

/**
 * The results page for a search. ``view`` is the tab ("" People, "connections"),
 * ``display`` how it is drawn ("" the list, "network"), ``person`` whose
 * connections the Connections tab shows.
 */
export function searchHref(
  config,
  { query = "", facet = "", page = 1, view = "", display = "", person = "" } = {},
) {
  const results = (config.app?.pages || []).find((item) => item.page_id === "results");
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (facet) params.set("facet", facet);
  if (view) params.set("view", view);
  if (display) params.set("display", display);
  if (person) params.set("person", person);
  if (page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return `#/${results?.url || "search"}${suffix ? `?${suffix}` : ""}`;
}

export function ontologyHref(config) {
  const page = (config.app?.pages || []).find((item) => item.page_id === "ontology");
  return `#/${page?.url || "ontology"}`;
}

export function profileHref(config, slug, { query = "" } = {}) {
  const page = (config.app?.pages || []).find((item) => item.page_id === "profile");
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  const suffix = params.toString();
  return `#/${page?.url || "p"}/${encodeURIComponent(slug)}${suffix ? `?${suffix}` : ""}`;
}

export function go(href) {
  window.location.hash = href.replace(/^#/, "");
}
