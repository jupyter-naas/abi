import {
  fetchConnections,
  fetchConnectionsNetwork,
  fetchSearch,
  fetchSearchNetwork,
} from "../../../lib/api.js";
import { avatarHtml, escapeHtml, flagHtml, highlight, ICONS, orgLogoHtml } from "../../../lib/dom.js";
import { profileHref, searchHref } from "../../../lib/routes.js";
import { apiUrl } from "../../../lib/config.js";
import { mountGraphView } from "../../../lib/graph-view.js";
import {
  connectionsLabel,
  DISPLAYS,
  personOfQuery,
  resultsState,
  TABS,
} from "../../../lib/results-state.js";
import { overflowTabs } from "../../../lib/tab-overflow.js";

function resultHtml(config, hit, tokens, query, facet = "", display = "") {
  const place = [hit.organization, ...(hit.place || [])].filter(Boolean);
  const snippet = hit.snippet || {};
  const connections = connectionsLabel(hit.connections_count);
  return `
    <article class="result">
      <div class="result-body">
        <p class="result-line">
          ${flagHtml(hit.country_code)}
          ${orgLogoHtml(hit.organization, hit.organization_logo)}
          <span>${escapeHtml(place.join(" › "))}</span>
          ${
            query && hit.hits
              ? `<span class="result-hits">${hit.hits} ${hit.hits === 1 ? "hit" : "hits"}</span>`
              : ""
          }
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
        ${
          hit.linkedin_url || connections
            ? `<p class="result-contact">${
                hit.linkedin_url
                  ? `<a class="contact-link" href="${escapeHtml(hit.linkedin_url)}"
                target="_blank" rel="noopener noreferrer"
                aria-label="${escapeHtml(`LinkedIn: ${hit.full_name || ""}`)}">${ICONS.linkedin_url}<span>LinkedIn</span></a>`
                  : ""
              }${
                hit.linkedin_url && connections
                  ? `<span class="result-contact-separator" aria-hidden="true">·</span>`
                  : ""
              }${
                connections
                  ? `<a class="result-connections" href="${searchHref(config, {
                      query,
                      facet,
                      view: "connections",
                      display,
                      person: hit.slug,
                    })}">${escapeHtml(connections)}</a>`
                  : ""
              }</p>`
            : ""
        }
      </div>
      ${avatarHtml(hit, "md")}
    </article>`;
}

/** The tabs of a search; each can be drawn as a list or as a network. */
export const VIEWS = TABS;

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

/** Mark the Network toggle as loading until the search's network has arrived. */
function prefetchNetwork(host, query, facet) {
  const tab = host.querySelector('.view-toggle [data-display="network"]');
  tab?.classList.add("is-loading");
  loadNetwork(query, facet)
    .catch(() => {})
    .finally(() => tab?.classList.remove("is-loading"));
}

export function viewOf(value) {
  return VIEWS.some((item) => item.id === value) ? value : "";
}

/**
 * The tabs, and in their top right corner the list/network toggle. Every link
 * keeps the search, the facet and the person: switching tab or display never
 * loses what was asked.
 */
function tabsHtml(config, { query, facet, view, display = "", person = "" }) {
  const tabs = TABS.map(
    (item) => `<a class="tab" data-view="${item.id || "people"}" href="${searchHref(config, {
      query,
      facet,
      view: item.id,
      display,
      person,
    })}"
      aria-current="${item.id === view}">${escapeHtml(item.label)}</a>`,
  ).join("");
  const toggle = DISPLAYS.map(
    (item) => `<a class="view-toggle-option" data-display="${item.id || "list"}" href="${searchHref(
      config,
      { query, facet, view, display: item.id, person },
    )}" aria-pressed="${item.id === display}">${escapeHtml(item.label)}</a>`,
  ).join("");
  return `<div class="tabbar">
    <nav class="tabs" aria-label="View">${tabs}</nav>
    <div class="view-toggle" role="group" aria-label="Display">${toggle}</div>
  </div>`;
}

function bodyHtml(config, results, tokens, query, facet, display) {
  if (!results.length) return emptyHtml(config, query);
  return results.map((hit) => resultHtml(config, hit, tokens, query, facet, display)).join("");
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

function errorDetailText(error) {
  const detail = error.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return "";
}

function errorHtml(error) {
  if (error.detail?.error === "missing_dataset") return missingDatasetHtml(error.detail);
  const extra = errorDetailText(error);
  const body = extra
    ? `${escapeHtml(error.message)}<br/>${escapeHtml(extra)}`
    : escapeHtml(error.message);
  return `<div class="empty-state error-block"><h2>Search failed</h2><p>${body}</p></div>`;
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
 * The Network view: the person graph page focused on the search. It opens
 * four hops out, far enough to reach the people's organizations (search,
 * match, act, person, organization). A person's node links to their profile.
 */
async function mountNetwork(host, { config, query, facet }) {
  host.innerHTML = `
    <div class="results results-network">
      ${tabsHtml(config, { query, facet, view: "", display: "network" })}
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
        for (const entity of network.data.entities || []) {
          // Served under this app's API: the same path the People list uses.
          if (entity.image) entity.image = apiUrl(entity.image);
        }
        return network;
      },
      { distance: 4 },
    );
    return dispose;
  } catch (error) {
    if (!graphEl.isConnected) return null;
    graphEl.outerHTML = error.empty ? emptyHtml(config, query) : errorHtml(error);
    return null;
  }
}

function tidyTabs(host) {
  const tabs = host.querySelector(".tabs");
  if (tabs) overflowTabs(tabs);
}

function connectionHtml(config, item, query) {
  const place = [item.organization, item.position].filter(Boolean).join(" · ");
  const connections = connectionsLabel(item.connections_count);
  return `
    <article class="result connection">
      <div class="result-body">
        <p class="result-line">
          ${flagHtml(item.country_code)}
          ${orgLogoHtml(item.organization, item.organization_logo)}
          <span>${escapeHtml(place)}</span>
        </p>
        <h2 class="result-title">
          <a href="${profileHref(config, item.slug, { query })}">${escapeHtml(item.full_name || item.slug)}</a>
        </h2>
        ${
          item.connected_on
            ? `<p class="result-headline">Connected on ${escapeHtml(formatDate(item.connected_on))}</p>`
            : ""
        }
        ${
          connections
            ? `<p class="result-contact"><a class="result-connections" href="${searchHref(config, {
                query,
                view: "connections",
                person: item.slug,
              })}">${escapeHtml(connections)}</a></p>`
            : ""
        }
      </div>
      ${avatarHtml(item, "md")}
    </article>`;
}

function formatDate(iso) {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function connectionsEmptyHtml(person) {
  if (!person) {
    return `<div class="empty-state">
      <h2>No one here has connections yet</h2>
      <p>Connections come from LinkedIn data exports imported into this app.</p>
    </div>`;
  }
  return `<div class="empty-state">
    <h2>No connections recorded for ${escapeHtml(person.full_name || person.slug)}</h2>
    <p>Connections come from LinkedIn data exports imported into this app.</p>
  </div>`;
}

/** Whose connections to show: the person in the URL, else the one the query names. */
async function connectionsPerson(state) {
  if (state.person) return state.person;
  if (!state.query) return "";
  const payload = await fetchSearch({ query: state.query, facet: state.facet });
  return personOfQuery(payload.results, state.query)?.slug || "";
}

/** The people of the search who have connections, most connected first. */
async function mountMostConnected(config, state, stats, body) {
  const { query, facet, display } = state;
  let payload;
  try {
    payload = await fetchSearch({ query, facet, page: state.page, sort: "connections" });
  } catch (error) {
    body.innerHTML = errorHtml(error);
    return;
  }
  const results = payload.results || [];
  if (!results.length) {
    stats.textContent = "";
    body.innerHTML = connectionsEmptyHtml(null);
    return;
  }
  stats.innerHTML = `${statsText(payload)} with connections${
    query ? ` for “${escapeHtml(query)}”` : ""
  }${payload.facet ? ` in ${escapeHtml(payload.facet)}` : ""}`;
  body.innerHTML = `${results
    .map((hit) => resultHtml(config, hit, payload.tokens || [], query, payload.facet, display))
    .join("")}${pagerHtml(config, payload, query, "connections")}`;
}

/** The Connections tab: the most connected people, or one person's connections. */
async function mountConnections(host, { config, state }) {
  const { query, facet, display } = state;
  host.innerHTML = `
    <div class="results${display === "network" ? " results-network" : ""}">
      ${tabsHtml(config, { ...state, view: "connections" })}
      <p class="stats">Finding connections…</p>
      <div class="connections-body"></div>
    </div>`;
  tidyTabs(host);
  const stats = host.querySelector(".stats");
  const body = host.querySelector(".connections-body");
  let slug = "";
  try {
    slug = await connectionsPerson(state);
  } catch (error) {
    body.outerHTML = errorHtml(error);
    return null;
  }
  if (!slug) {
    await mountMostConnected(config, state, stats, body);
    return null;
  }
  const whose = (payload) => {
    const name = escapeHtml(payload.person?.full_name || slug);
    const href = profileHref(config, slug, { query });
    const noun = payload.total === 1 ? "connection" : "connections";
    return `<a href="${href}">${name}</a> · ${payload.total} ${noun}`;
  };

  if (display === "network") {
    body.className = "profile-graph search-graph";
    try {
      return await mountGraphView(
        body,
        async () => {
          const network = structuredClone(await fetchConnectionsNetwork(slug));
          stats.innerHTML =
            network.shown < network.total
              ? `${whose(network)} · the ${network.shown} most recent drawn`
              : whose(network);
          if (!network.total) throw Object.assign(new Error("empty"), { person: network.person });
          for (const person of network.data.people || []) {
            if (person.slug) person.href = profileHref(config, person.slug, { query });
          }
          for (const entity of network.data.entities || []) {
            if (entity.image) entity.image = apiUrl(entity.image);
          }
          return network;
        },
        { distance: 2 },
      );
    } catch (error) {
      if (!body.isConnected) return null;
      body.className = "connections-body";
      body.innerHTML = error.person ? connectionsEmptyHtml(error.person) : errorHtml(error);
      return null;
    }
  }

  try {
    const payload = await fetchConnections(slug);
    stats.innerHTML = whose(payload);
    body.innerHTML = payload.total
      ? payload.results.map((item) => connectionHtml(config, item, query)).join("")
      : connectionsEmptyHtml(payload.person);
  } catch (error) {
    body.innerHTML = errorHtml(error);
  }
  return null;
}

export async function mountResults(host, { config, params }) {
  const state = resultsState(params, config.app?.default_results_view ?? "");
  const { query, facet, view, display } = state;
  const requestedPage = state.page;

  if (view === "connections") {
    const dispose = await mountConnections(host, { config, state });
    return { showTopbarSearch: true, query, teardown: dispose || undefined };
  }

  if (display === "network") {
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
      ${tabsHtml(config, { query, facet: payload.facet, view, display })}
      <p class="stats">${statsText(payload)}${
        query ? ` for “${escapeHtml(query)}”` : ""
      }${payload.facet ? ` in ${escapeHtml(payload.facet)}` : ""}</p>
      ${noticeHtml}
      ${bodyHtml(config, results, tokens, query, payload.facet, display)}
      ${pagerHtml(config, payload, query, view)}
    </div>`;
  tidyTabs(host);
  // Not awaited: the list is already on screen.
  if (results.length) prefetchNetwork(host, query, payload.facet);

  return { showTopbarSearch: true, query };
}
