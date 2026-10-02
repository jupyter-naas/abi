import { fetchSearch } from "../../../lib/api.js";
import { avatarHtml, escapeHtml, flagHtml, highlight } from "../../../lib/dom.js";
import { profileHref, searchHref } from "../../../lib/routes.js";

function resultHtml(config, hit, tokens, query) {
  const place = [hit.organization, ...(hit.place || [])].filter(Boolean);
  const snippet = hit.snippet || {};
  return `
    <article class="result">
      <div class="result-body">
        <p class="result-line">
          ${flagHtml(hit.country_code)}
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

function tabsHtml(config, payload, query) {
  const facets = payload.facets || [];
  if (facets.length < 2) return "";
  const all = `<a class="tab" href="${searchHref(config, { query })}" aria-current="${!payload.facet}">
      ${escapeHtml(config.search?.all_facet_label || "All")}
      <span class="tab-count">${payload.facets.reduce((sum, facet) => sum + facet.count, 0)}</span>
    </a>`;
  const rest = facets
    .map(
      (facet) => `<a class="tab" href="${searchHref(config, { query, facet: facet.value })}"
        aria-current="${payload.facet === facet.value}">
        ${escapeHtml(facet.value)}<span class="tab-count">${facet.count}</span>
      </a>`,
    )
    .join("");
  return `<nav class="tabs" aria-label="${escapeHtml(config.search?.facet_label || "Filter")}">${all}${rest}</nav>`;
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

function pagerHtml(config, payload, query) {
  const pages = payload.pages || 1;
  if (pages < 2) return "";
  const current = payload.page || 1;
  const href = (page) => searchHref(config, { query, facet: payload.facet, page });
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

export async function mountResults(view, { config, params }) {
  const query = params.get("q") || "";
  const facet = params.get("facet") || "";
  const requestedPage = Math.max(1, parseInt(params.get("page") || "1", 10) || 1);
  view.innerHTML = `<div class="results"><p class="stats">Searching…</p></div>`;

  let payload;
  try {
    payload = await fetchSearch({ query, facet, page: requestedPage });
  } catch (error) {
    view.innerHTML = `<div class="results">${
      error.detail?.error === "missing_dataset"
        ? missingDatasetHtml(error.detail)
        : `<div class="empty-state error-block"><h2>Search failed</h2><p>${escapeHtml(error.message)}</p></div>`
    }</div>`;
    return { showTopbarSearch: true, query };
  }

  const tokens = payload.tokens || [];
  const results = payload.results || [];
  const noticeHtml =
    payload.mode === "any"
      ? `<p class="notice">No one matches every word. Showing people who match some of them.</p>`
      : "";

  view.innerHTML = `
    <div class="results">
      ${tabsHtml(config, payload, query)}
      <p class="stats">${statsText(payload)}${
        query ? ` for “${escapeHtml(query)}”` : ""
      }${payload.facet ? ` in ${escapeHtml(payload.facet)}` : ""}</p>
      ${noticeHtml}
      ${
        results.length
          ? results.map((hit) => resultHtml(config, hit, tokens, query)).join("")
          : emptyHtml(config, query)
      }
      ${pagerHtml(config, payload, query)}
    </div>`;

  return { showTopbarSearch: true, query };
}
