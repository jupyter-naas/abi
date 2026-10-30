/**
 * What the results page shows, read from its URL. Pure, so it is tested
 * without a browser (results-state.test.js).
 *
 *   view     the tab: "" People, "connections" Connections
 *   display  how the tab is drawn: "" the list, "network"
 *   person   whose connections the Connections tab shows
 *
 * The page used to have a Network tab (view=network); such a link opens the
 * People tab drawn as a network.
 */

export const TABS = [
  { id: "", label: "People" },
  { id: "connections", label: "Connections" },
];

export const DISPLAYS = [
  { id: "", label: "List" },
  { id: "network", label: "Network" },
];

const ids = (items) => new Set(items.map((item) => item.id));

export function resultsState(params, defaultDisplay = "") {
  const rawView = params.get("view") || "";
  const legacyNetwork = rawView === "network";
  const view = !legacyNetwork && ids(TABS).has(rawView) ? rawView : "";
  const rawDisplay = params.get("display");
  let display = ids(DISPLAYS).has(rawDisplay) ? rawDisplay : "";
  if (legacyNetwork) display = "network";
  else if (rawDisplay === null && !rawView) display = ids(DISPLAYS).has(defaultDisplay) ? defaultDisplay : "";
  return {
    query: params.get("q") || "",
    facet: params.get("facet") || "",
    view,
    display,
    person: params.get("person") || "",
    page: Math.max(1, parseInt(params.get("page") || "1", 10) || 1),
  };
}

function folded(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * The person a search is about: the one result whose name is the query.
 * Nobody when no name or several names match, so the Connections tab never
 * guesses between two people.
 */
export function personOfQuery(results, query) {
  const wanted = folded(query);
  if (!wanted) return null;
  const named = (results || []).filter((hit) => folded(hit.full_name) === wanted);
  return named.length === 1 ? named[0] : null;
}

/** "3 connections", "1 connection", or "" for none. */
export function connectionsLabel(count) {
  if (!count) return "";
  return `${count} ${count === 1 ? "connection" : "connections"}`;
}
