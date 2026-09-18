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
  view.innerHTML = `<div class="results"><p class="stats">Searching…</p></div>`;

  let payload;
  try {
    payload = await fetchSearch({ query, facet });
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
      <p class="stats">${payload.total} ${payload.total === 1 ? "person" : "people"}${
        query ? ` for “${escapeHtml(query)}”` : ""
      }${payload.facet ? ` in ${escapeHtml(payload.facet)}` : ""}</p>
      ${noticeHtml}
      ${
        results.length
          ? results.map((hit) => resultHtml(config, hit, tokens, query)).join("")
          : emptyHtml(config, query)
      }
    </div>`;

  return { showTopbarSearch: true, query };
}
