/** Reads. The browser never touches the dataset service directly. */

import { API_BASE } from "./config.js";
import { isBundledInNexus, nexusAuthHeaders, nexusWorkspaceId } from "./nexus.js";

function apiPath(path) {
  const joined = `${API_BASE}${path}`;
  if (!isBundledInNexus()) return joined;
  const workspaceId = nexusWorkspaceId();
  if (!workspaceId || joined.includes("workspace_id=")) return joined;
  const sep = joined.includes("?") ? "&" : "?";
  return `${joined}${sep}workspace_id=${encodeURIComponent(workspaceId)}`;
}

async function getJson(path) {
  return readJson(path, await fetch(apiPath(path), { headers: nexusAuthHeaders() }));
}

/** A multipart POST (an upload), under the same session as the reads. */
async function postForm(path, form) {
  return readJson(
    path,
    await fetch(apiPath(path), { method: "POST", headers: nexusAuthHeaders(), body: form }),
  );
}

async function readJson(path, response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(`${path} → ${response.status}`);
    error.status = response.status;
    error.detail = body?.detail ?? body;
    throw error;
  }
  return body;
}

export function fetchSearch({ query = "", facet = "", page = 1, sort = "" } = {}) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (facet) params.set("facet", facet);
  if (page > 1) params.set("page", String(page));
  if (sort) params.set("sort", sort);
  const suffix = params.toString();
  return getJson(`/search${suffix ? `?${suffix}` : ""}`);
}

/** The Network view of a search: the query, what it matched and the people it leads to. */
export function fetchSearchNetwork({ query = "", facet = "" } = {}) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (facet) params.set("facet", facet);
  const suffix = params.toString();
  return getJson(`/search/network${suffix ? `?${suffix}` : ""}`);
}

export function fetchSuggestions(query) {
  return getJson(`/suggest?q=${encodeURIComponent(query)}`);
}

export function fetchPerson(slug) {
  return getJson(`/people/${encodeURIComponent(slug)}`);
}

/** The person graph page's data, built live from the graph, opened on this person. */
export function fetchPersonGraph(slug) {
  return getJson(`/people/${encodeURIComponent(slug)}/graph`);
}

export function fetchQueryResults(slug, queryName, { maxRows = 50 } = {}) {
  const params = new URLSearchParams();
  if (maxRows !== 50) params.set("max_rows", String(maxRows));
  const suffix = params.toString();
  return getJson(
    `/people/${encodeURIComponent(slug)}/queries/${encodeURIComponent(queryName)}/run${
      suffix ? `?${suffix}` : ""
    }`,
  );
}

export function fetchOntology() {
  return getJson("/ontology");
}

/** Who the person is connected to (the Connections tab). */
export function fetchConnections(slug) {
  return getJson(`/people/${encodeURIComponent(slug)}/connections`);
}

/** The person and their connections, as a graph page payload. */
export function fetchConnectionsNetwork(slug) {
  return getJson(`/people/${encodeURIComponent(slug)}/connections/network`);
}

/** Whose LinkedIn export the viewer may import: themselves, or anyone if admin. */
export function fetchLinkedInOwners() {
  return getJson("/linkedin/owners");
}

/** The Connections tab's network before a person is chosen: the most connected. */
export function fetchMostConnectedNetwork({ query = "", facet = "" } = {}) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (facet) params.set("facet", facet);
  const suffix = params.toString();
  return getJson(`/connections/network${suffix ? `?${suffix}` : ""}`);
}

export function startLinkedInImport(form) {
  return postForm("/linkedin/imports", form);
}

export function fetchLinkedInImport(runId) {
  return getJson(`/linkedin/imports/${encodeURIComponent(runId)}`);
}

export async function cancelLinkedInImport(runId) {
  return readJson(
    `/linkedin/imports/${encodeURIComponent(runId)}/cancel`,
    await fetch(apiPath(`/linkedin/imports/${encodeURIComponent(runId)}/cancel`), {
      method: "POST",
      headers: nexusAuthHeaders(),
    }),
  );
}
