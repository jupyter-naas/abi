import { fetchSearch, fetchSearchNetwork } from "../../../lib/api.js";
import { avatarHtml, escapeHtml, flagHtml, highlight, orgLogoHtml } from "../../../lib/dom.js";
import { profileHref, searchHref } from "../../../lib/routes.js";
import { mountGraphView } from "../../../lib/graph-view.js";
import { overflowTabs } from "../../../lib/tab-overflow.js";

function resultHtml(config, hit, tokens, query) {
  const place = [hit.organization, ...(hit.place || [])].filter(Boolean);
  const snippet = hit.snippet || {};
  return `
    <article class="result">
      <div class="result-body">
        <p class="result-line">
          ${flagHtml(hit.country_code)}
          ${orgLogoHtml(hit.organization, hit.organization_logo)}
          <span>${escapeHtml(place.join(" › "))}</span>
        </p>
        <h2 class="result-title">
          <a href="${profileHref(config, hit.slug, { query })}">${highlight(hit.full_name, tokens, "b")}</a>
        </h2>
        <p class="result-headline">${highlight(hit.headline || "", tokens, "b")}</p>
        ${
          snippet.text
            ? `<p class="result-snippet">${
                snippet.label
                  ? `<span class="result-snippet-label">${escapeHtml(snippet.label)}: </span>`
                  : ""
              }${highlight(snippet.text, tokens, "b")}</p>`
            : ""
        }
      </div>
      ${avatarHtml(hit, "md")}
    </article>`;
}

/**
 * The ways to look at a search: the list of people, then its network (the
 * search at the centre, what it matched, and the people it leads to).
 */
export const VIEWS = [
  { id: "", label: "People" },
  { id: "network", label: "Network" },
];

// The network of each search asked for in this page's lifetime. The People view
// starts it in the background, so the Network tab is ready, or on its way,
// when it is opened; the first build of a search can take seconds.
const networkRequests = new Map();

function loadNetwork(query, facet) {
  const key = JSON.stringify([query, facet]);
  if (!networkRequests.has(key)) {
    const request = fetchSearchNetwork({ query, facet });
    // A failed request is not kept: the next visit asks again.
    request.catch(() => networkRequests.delete(key));
    networkRequests.set(key, request);
  }
  return networkRequests.get(key);
}

/** Mark the Network tab as loading until its network has arrived. */
function prefetchNetwork(host, query, facet) {
  const tab = host.querySelector('.tabs .tab[data-view="network"]');
  tab?.classList.add("is-loading");
  loadNetwork(query, facet)
    .catch(() => {})
    .finally(() => tab?.classList.remove("is-loading"));
}

export function viewOf(value) {
  return VIEWS.some((item) => item.id === value) ? value : "";
}

function tabsHtml(config, { query, facet, view }) {
  const tabs = VIEWS.map(
    (item) => `<a class="tab" data-view="${item.id || "people"}" href="${searchHref(config, { query, facet, view: item.id })}"
      aria-current="${item.id === view}">${escapeHtml(item.label)}</a>`,
  ).join("");
  return `<nav class="tabs" aria-label="View">${tabs}</nav>`;
}

function bodyHtml(config, results, tokens, query) {
  if (!results.length) return emptyHtml(config, query);
  return results.map((hit) => resultHtml(config, hit, tokens, query)).join("");
}

/**
 * The page numbers to show: the first, the last and a window round the current
 * one, with a gap marked where numbers are skipped. Pure, so it can be reasoned
 * about without a browser.
 */
export function pageWindow(current, pages, radius = 2) {
  const shown = new Set([1, pages]);
  for (let n = current - radius; n <= current + radius; n += 1) {
    if (n >= 1 && n <= pages) shown.add(n);
  }
  const sorted = [...shown].sort((a, b) => a - b);
  const out = [];
  sorted.forEach((n, index) => {
    const gap = index ? n - sorted[index - 1] - 1 : 0;
    // An ellipsis stands for two pages or more; a single skipped page is shown.
    if (gap === 1) out.push(n - 1);
    else if (gap > 1) out.push(null);
    out.push(n);
  });
  return out;
}

function pagerHtml(config, payload, query, view = "") {
  const pages = payload.pages || 1;
  if (pages < 2) return "";
  const current = payload.page || 1;
  const href = (page) => searchHref(config, { query, facet: payload.facet, page, view });
  const link = (page, label, { disabled = false, ariaLabel = "" } = {}) =>
    disabled
      ? `<span class="page page-disabled" aria-disabled="true">${label}</span>`
      : `<a class="page" href="${href(page)}"${ariaLabel ? ` aria-label="${ariaLabel}"` : ""}>${label}</a>`;
  const numbers = pageWindow(current, pages)
    .map((n) =>
      n === null
        ? `<span class="page page-gap" aria-hidden="true">…</span>`
        : n === current
          ? `<span class="page page-current" aria-current="page">${n}</span>`
          : link(n, n, { ariaLabel: `Page ${n}` }),
    )
    .join("");
  return `<nav class="pager" aria-label="Pages">
    ${link(current - 1, "‹ Previous", { disabled: current <= 1 })}
    ${numbers}
    ${link(current + 1, "Next ›", { disabled: current >= pages })}
  </nav>`;
}

function statsText(payload) {
  const noun = payload.total === 1 ? "person" : "people";
  const shown = (payload.results || []).length;
  // "101–200 of 847 people" once there is more than one page; otherwise the plain count.
  if ((payload.pages || 1) < 2 || !shown) return `${payload.total} ${noun}`;
  const first = (payload.page - 1) * payload.page_size + 1;
  return `${first}–${first + shown - 1} of ${payload.total} ${noun}`;
}

function emptyHtml(config, query) {
  return `
    <div class="empty-state">
      <h2>No one matches ${escapeHtml(query ? `“${query}”` : "that")}</h2>
      <p>Try a different word, or search for a skill, a place or a school.</p>
      <p><a class="chip" href="${searchHref(config, {})}">Browse everyone</a></p>
    </div>`;
}

export function missingDatasetHtml(detail) {
  const command = detail?.command || "make people-datasets";
  return `
    <div class="empty-state error-block">
      <h2>No people have been exported yet</h2>
      <p>${escapeHtml(detail?.message?.split("\n")[0] || "The datasets this app reads do not exist.")}</p>
      <p>Build them from the graph:</p>
      <code>${escapeHtml(command)}</code>
    </div>`;
}

function errorHtml(error) {
  return error.detail?.error === "missing_dataset"
    ? missingDatasetHtml(error.detail)
    : `<div class="empty-state error-block"><h2>Search failed</h2><p>${escapeHtml(error.message)}</p></div>`;
}

function networkStatsText(network, query) {
  const noun = network.total === 1 ? "person" : "people";
  const counted =
    network.shown < network.total
      ? `Top ${network.shown} of ${network.total} ${noun}`
      : `${network.total} ${noun}`;
  return `${counted}${query ? ` for “${escapeHtml(query)}”` : ""}${
    network.facet ? ` in ${escapeHtml(network.facet)}` : ""
  }`;
}

/**
 * The Network view: the person graph page focused on the search query. It
 * opens three hops out, far enough to reach the people (query, match, what
 * matched, person). A person's node links to their profile.
 */
async function mountNetwork(host, { config, query, facet }) {
  host.innerHTML = `
    <div class="results results-network">
      ${tabsHtml(config, { query, facet, view: "network" })}
      <p class="stats">Drawing the network…</p>
      <div class="profile-graph search-graph"></div>
    </div>`;
  const tabs = host.querySelector(".tabs");
  if (tabs) overflowTabs(tabs);
  const stats = host.querySelector(".stats");
  const graphEl = host.querySelector(".search-graph");
  try {
    const dispose = await mountGraphView(
      graphEl,
      async () => {
        const network = structuredClone(await loadNetwork(query, facet));
        stats.innerHTML = networkStatsText(network, query);
        if (!network.total) throw Object.assign(new Error("empty"), { empty: true });
        for (const person of network.data.people || []) {
          if (person.slug) person.href = profileHref(config, person.slug, { query });
        }
        return network;
      },
      { distance: 3 },
    );
    return dispose;
  } catch (error) {
    if (!graphEl.isConnected) return null;
    graphEl.outerHTML = error.empty ? emptyHtml(config, query) : errorHtml(error);
    return null;
  }
}

export async function mountResults(host, { config, params }) {
  const query = params.get("q") || "";
  const facet = params.get("facet") || "";
  const view = viewOf(params.get("view") || "");
  const requestedPage = Math.max(1, parseInt(params.get("page") || "1", 10) || 1);

  if (view === "network") {
    const dispose = await mountNetwork(host, { config, query, facet });
    return { showTopbarSearch: true, query, teardown: dispose || undefined };
  }

  host.innerHTML = `<div class="results"><p class="stats">Searching…</p></div>`;
  let payload;
  try {
    payload = await fetchSearch({ query, facet, page: requestedPage });
  } catch (error) {
    host.innerHTML = `<div class="results">${errorHtml(error)}</div>`;
    return { showTopbarSearch: true, query };
  }

  const tokens = payload.tokens || [];
  const results = payload.results || [];
  const noticeHtml =
    payload.mode === "any"
      ? `<p class="notice">No one matches every word. Showing people who match some of them.</p>`
      : "";

  host.innerHTML = `
    <div class="results">
      ${tabsHtml(config, { query, facet: payload.facet, view })}
      <p class="stats">${statsText(payload)}${
        query ? ` for “${escapeHtml(query)}”` : ""
      }${payload.facet ? ` in ${escapeHtml(payload.facet)}` : ""}</p>
      ${noticeHtml}
      ${bodyHtml(config, results, tokens, query)}
      ${pagerHtml(config, payload, query, view)}
    </div>`;
  const tabs = host.querySelector(".tabs");
  if (tabs) overflowTabs(tabs);
  // Not awaited: the list is already on screen.
  if (results.length) prefetchNetwork(host, query, payload.facet);

  return { showTopbarSearch: true, query };
}
