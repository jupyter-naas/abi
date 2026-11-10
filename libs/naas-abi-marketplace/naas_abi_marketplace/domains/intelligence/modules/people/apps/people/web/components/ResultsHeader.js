/**
 * The results page's header: its tabs (People, Connections) and the line
 * counting what is shown. A component of its own because it stays put: it
 * sticks under the topbar while a list scrolls, and sits above a network that
 * takes the rest of the page, as wide as the window.
 *
 * How the tab is drawn (List, Network) is switched from the topbar, beside the
 * search box, the way a profile switches Resume and Graph (``displaySwitch``).
 */

import { escapeHtml } from "../lib/dom.js";
import { DISPLAYS, TABS } from "../lib/results-state.js";
import { searchHref } from "../lib/routes.js";
import { overflowTabs } from "../lib/tab-overflow.js";

/**
 * The tabs. Every link keeps the search, the facet, the display and the
 * person: switching tab never loses what was asked.
 */
export function tabsHtml(config, { query, facet, view, display = "", person = "" }) {
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
  return `<div class="tabbar"><nav class="tabs" aria-label="View">${tabs}</nav></div>`;
}

/**
 * The List / Network switch, for the topbar (``state.topbarEnd``). Its links
 * keep the search, the facet, the tab and the person.
 */
export function displaySwitch(config, { query, facet, view, display = "", person = "" }) {
  const element = document.createElement("div");
  element.className = "profile-view-switch results-display-switch";
  element.setAttribute("role", "group");
  element.setAttribute("aria-label", "Display");
  element.innerHTML = DISPLAYS.map(
    (item) => `<a class="profile-view-option" data-display="${item.id || "list"}" href="${searchHref(
      config,
      { query, facet, view, display: item.id, person },
    )}" aria-pressed="${item.id === display}">${escapeHtml(item.label)}</a>`,
  ).join("");
  return element;
}

/** The header: tabs and the stats line (HTML, filled in later if empty). */
export function resultsHeaderHtml(config, tabs, statsHtml = "") {
  return `<header class="results-header">
    ${tabsHtml(config, tabs)}
    <p class="stats">${statsHtml}</p>
  </header>`;
}

/** Lay the header's tabs out (the ones that do not fit go behind "N more"). */
export function wireResultsHeader(host) {
  const tabs = host.querySelector(".results-header .tabs");
  if (tabs) overflowTabs(tabs);
}
