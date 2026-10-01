import { searchBoxHtml, wireSearch } from "../../SearchBox.js";
import { logoHtml } from "../../../lib/config.js";
import { escapeHtml } from "../../../lib/dom.js";
import { ontologyHref, searchHref } from "../../../lib/routes.js";

export function mountHome(view, { config }) {
  const examples = config.search?.example_queries || [];
  view.innerHTML = `
    <div class="home">
      ${logoHtml(config)}
      <h1 class="home-title">${escapeHtml(config.brand?.name || "People")}</h1>
      <p class="home-subtitle">${escapeHtml(config.brand?.description || "")}</p>
      <div class="home-search">${searchBoxHtml(config, { autofocus: true })}</div>
      ${
        examples.length
          ? `<div class="home-examples"><span>Try</span>${examples
              .map(
                (example) =>
                  `<a class="chip" href="${searchHref(config, { query: example })}">${escapeHtml(example)}</a>`,
              )
              .join("")}</div>`
          : ""
      }
      <p class="home-ontology">
        <a class="home-ontology-link" href="${ontologyHref(config)}">Personnel ontology</a>
      </p>
    </div>`;
  wireSearch(view, config);
  return { showTopbarSearch: false };
}
