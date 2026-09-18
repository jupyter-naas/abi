import { fetchPerson, fetchQueryResults } from "../../../lib/api.js";
import {
  avatarHtml,
  escapeHtml,
  flagHtml,
  formatQueryLabel,
  highlight,
  ICONS,
} from "../../../lib/dom.js";
import { profileHref, searchHref } from "../../../lib/routes.js";
import { sectionHtml } from "../../profile/sections.js";
import { missingDatasetHtml } from "../results/ResultsPage.js";

function relatedHtml(config, related, query) {
  const people = related?.people || [];
  if (!people.length) return "";
  return `
    <section class="card profile-sidebar-card">
      <h2>More in ${escapeHtml(related.value)}</h2>
      <ul class="related">
        ${people
          .map(
            (person) => `
          <li>
            <a href="${profileHref(config, person.slug, { query })}">
              ${avatarHtml(person, "sm")}
              <span>
                <span class="related-name">${escapeHtml(person.full_name)}</span><br />
                <span class="related-headline">${escapeHtml(person.headline || "")}</span>
              </span>
            </a>
          </li>`,
          )
          .join("")}
      </ul>
    </section>`;
}

const DEFAULT_KNOWLEDGE_GRAPH = {
  iri: "http://ontology.naas.ai/graph/personnel",
  label: "Personnel",
};

function resolveKnowledgeGraph(knowledgeGraph, fallback) {
  const fromApi = knowledgeGraph?.iri || knowledgeGraph?.label ? knowledgeGraph : null;
  const fromConfig = fallback?.iri || fallback?.label ? fallback : null;
  const graph = fromApi || fromConfig || DEFAULT_KNOWLEDGE_GRAPH;
  return {
    iri: graph.iri || DEFAULT_KNOWLEDGE_GRAPH.iri,
    label: graph.label || DEFAULT_KNOWLEDGE_GRAPH.label,
  };
}

function sourcesSidebarHtml(section, knowledgeGraph) {
  const graph = resolveKnowledgeGraph(knowledgeGraph);
  return `
    <section class="card profile-sidebar-card" id="section-sources">
      <h2>${escapeHtml(section?.label || "Sources")}</h2>
      <ul class="sources source-graph-list">
        <li>
          <span class="source-info-wrap">
            <span class="source-graph-name">${escapeHtml(graph.label)}</span>
            <button type="button" class="source-info" aria-label="Knowledge graph details for ${escapeHtml(
              graph.label,
            )}">i</button>
            <span class="source-info-popover" role="tooltip">
              <span class="source-info-line"><strong>Label</strong> ${escapeHtml(graph.label)}</span>
              <span class="source-info-line"><strong>Graph</strong> ${escapeHtml(graph.iri)}</span>
            </span>
          </span>
        </li>
      </ul>
    </section>`;
}

function normalizeCompetencyQueries(queries) {
  return (queries || []).map((entry) => {
    const name = entry.name || entry.label || "";
    return {
      ...entry,
      name,
      label: formatQueryLabel(name),
    };
  });
}

function sparqlSidebarHtml(competencyQueries) {
  const queries = competencyQueries || [];
  const body = queries.length
    ? `<ul class="sparql-query-list">${queries
        .map(
          (entry, index) =>
            `<li><button type="button" class="sparql-query-btn" data-query-index="${index}">${escapeHtml(
              entry.label || entry.name,
            )}</button></li>`,
        )
        .join("")}</ul>`
    : `<p class="empty">No competency queries configured.</p>`;
  return `
    <section class="card profile-sidebar-card" id="section-sparql-query">
      <h2>SparqlQuery</h2>
      ${body}
    </section>`;
}

function sparqlModalShell() {
  return `
    <div class="sparql-modal" id="sparql-modal" hidden>
      <div class="sparql-modal-backdrop" data-sparql-modal-close tabindex="-1"></div>
      <div class="sparql-modal-panel" role="dialog" aria-modal="true" aria-labelledby="sparql-modal-title">
        <button type="button" class="sparql-modal-close" data-sparql-modal-close aria-label="Close">×</button>
        <p class="sparql-modal-kicker">SPARQL</p>
        <h2 class="sparql-modal-title" id="sparql-modal-title"></h2>
        <pre class="sparql-modal-query" id="sparql-modal-query"></pre>
        <div class="sparql-modal-results" id="sparql-modal-results"></div>
      </div>
    </div>`;
}

function sparqlResultsHtml(result) {
  const columns = result?.columns || [];
  const rows = result?.rows || [];
  if (!columns.length) {
    return `<p class="sparql-results-empty">No rows returned.</p>`;
  }
  const truncated = result.truncated
    ? ` (first ${rows.length} shown)`
    : "";
  const head = `<tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>`;
  const body = rows
    .map(
      (row) =>
        `<tr>${row
          .map((cell) => `<td>${escapeHtml(cell ?? "")}</td>`)
          .join("")}</tr>`,
    )
    .join("");
  return `
    <h3 class="sparql-results-title">Results</h3>
    <p class="sparql-results-meta">${result.row_count} row${result.row_count === 1 ? "" : "s"}${escapeHtml(truncated)}</p>
    <div class="sparql-results-scroll">
      <table class="sparql-results-table">
        <thead>${head}</thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function wireSparqlModal(view, competencyQueries, slug) {
  const modal = view.querySelector("#sparql-modal");
  if (!modal || !competencyQueries?.length) return;

  const titleEl = modal.querySelector("#sparql-modal-title");
  const queryEl = modal.querySelector("#sparql-modal-query");
  const resultsEl = modal.querySelector("#sparql-modal-results");
  const closeButtons = modal.querySelectorAll("[data-sparql-modal-close]");
  let lastFocus = null;
  let runToken = 0;

  const close = () => {
    modal.hidden = true;
    document.body.classList.remove("sparql-modal-open");
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus();
    }
  };

  const open = async (index) => {
    const entry = competencyQueries[Number(index)];
    if (!entry) return;
    lastFocus = document.activeElement;
    titleEl.textContent = entry.label || entry.name;
    const kicker = modal.querySelector(".sparql-modal-kicker");
    if (kicker) {
      kicker.textContent = "SPARQL";
    }
    queryEl.textContent = entry.text;
    resultsEl.innerHTML = `<p class="sparql-results-status">Running query…</p>`;
    modal.hidden = false;
    document.body.classList.add("sparql-modal-open");
    modal.querySelector(".sparql-modal-close")?.focus();

    const token = ++runToken;
    try {
      const result = await fetchQueryResults(slug, entry.name);
      if (token !== runToken) return;
      resultsEl.innerHTML = sparqlResultsHtml(result);
    } catch {
      if (token !== runToken) return;
      resultsEl.innerHTML = `<p class="sparql-results-empty">Could not run this query on the knowledge graph.</p>`;
    }
  };

  view.addEventListener("click", (event) => {
    const button = event.target.closest(".sparql-query-btn");
    if (!button || !view.contains(button)) return;
    event.preventDefault();
    open(button.dataset.queryIndex);
  });

  closeButtons.forEach((button) => button.addEventListener("click", close));

  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  });
}

function notFoundHtml(config, slug) {
  return `
    <div class="results">
      <div class="empty-state">
        <h2>No profile for “${escapeHtml(slug)}”</h2>
        <p>The link may be out of date, or that person may not be in this directory.</p>
        <p><a class="chip" href="${searchHref(config, {})}">Browse everyone</a></p>
      </div>
    </div>`;
}

export async function mountProfile(view, { config, params, slug }) {
  const configKnowledgeGraph = config?.knowledge_graph;
  const query = params.get("q") || "";
  view.innerHTML = `<div class="profile"><p class="stats">Loading…</p></div>`;

  let person;
  try {
    person = await fetchPerson(slug);
  } catch (error) {
    view.innerHTML =
      error.detail?.error === "missing_dataset"
        ? `<div class="results">${missingDatasetHtml(error.detail)}</div>`
        : notFoundHtml(config, slug);
    return { showTopbarSearch: true, query, title: config.brand?.name };
  }

  const tokens = query
    ? query
        .normalize("NFKD")
        .replace(/\p{Diacritic}/gu, "")
        .toLowerCase()
        .split(/[^a-z0-9+]+/)
        .filter(Boolean)
    : [];

  const sections = person.sections || [];
  const competencyQueries = normalizeCompetencyQueries(person.competency_queries);
  const knowledgeGraph = resolveKnowledgeGraph(person.knowledge_graph, configKnowledgeGraph);
  const sideIds = new Set(["sources"]);
  const mainSections = sections.filter((section) => !sideIds.has(section.id));
  const sourcesSection = sections.find((section) => section.id === "sources");
  const place = [person.organization, ...(person.place || [])].filter(Boolean);

  view.innerHTML = `
    <div class="profile">
      <div class="profile-columns">
        <div class="profile-main">
          <div class="intro">
            <div class="intro-cover" aria-hidden="true"></div>
            <div class="intro-body">
            ${avatarHtml(person, "md").replace("avatar-md", "avatar-md intro-photo")}
            <h1 class="intro-name">${highlight(person.full_name, tokens)}</h1>
            <p class="intro-headline">${highlight(person.headline || "", tokens)}</p>
            <p class="intro-place">${flagHtml(person.country_code)}${ICONS.place}
              <span>${escapeHtml(place.join(" · "))}</span></p>
            ${person.quote ? `<p class="intro-quote">${highlight(person.quote, tokens)}</p>` : ""}
            ${
              person.facts?.length
                ? `<dl class="facts">${person.facts
                    .map(
                      (fact) => `<div class="fact">
                        <dt class="fact-label">${escapeHtml(fact.label)}</dt>
                        <dd class="fact-value">${escapeHtml(fact.value)}</dd>
                      </div>`,
                    )
                    .join("")}</dl>`
                : ""
            }
            </div>
          </div>
          ${mainSections.map((section) => sectionHtml(section, tokens)).join("")}
        </div>
        <aside class="profile-sidebar" aria-label="Profile sidebar">
          ${sourcesSidebarHtml(sourcesSection, knowledgeGraph)}
          ${sparqlSidebarHtml(competencyQueries)}
          ${relatedHtml(config, person.related, query)}
        </aside>
      </div>
      ${sparqlModalShell()}
    </div>`;

  wireSparqlModal(view, competencyQueries, slug);

  return { showTopbarSearch: true, query, title: `${person.full_name} · ${config.brand?.name}` };
}
