/** Reads. The browser never touches the dataset service directly. */

import { API_BASE } from "./config.js";

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(`${path} → ${response.status}`);
    error.status = response.status;
    error.detail = body?.detail ?? body;
    throw error;
  }
  return body;
}

export function fetchSearch({ query = "", facet = "", page = 1 } = {}) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (facet) params.set("facet", facet);
  if (page > 1) params.set("page", String(page));
  const suffix = params.toString();
  return getJson(`/search${suffix ? `?${suffix}` : ""}`);
}

export function fetchSuggestions(query) {
  return getJson(`/suggest?q=${encodeURIComponent(query)}`);
}

export function fetchPerson(slug) {
  return getJson(`/people/${encodeURIComponent(slug)}`);
}
