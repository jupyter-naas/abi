/** Workspace context when the app runs inside Nexus (iframe): the signed-in
 * user's token and the workspace the cockpit is opened in, which the cockpit API
 * requires. */

function parentWindow() {
  try {
    return window.parent !== window && window.parent.location.pathname
      ? window.parent
      : null;
  } catch {
    return null;
  }
}

export function nexusWorkspaceId() {
  const parent = parentWindow();
  const path = parent ? parent.location.pathname : "";
  const match = String(path).match(/\/workspace\/([^/?#]+)/);
  if (match) return match[1];
  const param = new URLSearchParams(window.location.search).get("workspace");
  if (param) return param;
  const referrer = String(document.referrer || "").match(/\/workspace\/([^/?#]+)/);
  return referrer ? referrer[1] : null;
}

export function nexusAuthHeaders() {
  const parent = parentWindow() || window;
  try {
    const raw = parent.localStorage.getItem("nexus-auth");
    const token = raw ? JSON.parse(raw)?.state?.token || null : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export function isBundledInNexus() {
  return window.location.pathname.startsWith("/app-html/");
}

/** A cockpit API URL, with the workspace the cockpit is opened in. */
export function cockpitUrl(path) {
  const workspaceId = nexusWorkspaceId();
  if (!workspaceId) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}workspace_id=${encodeURIComponent(workspaceId)}`;
}

/** fetch() for the cockpit API, as the signed-in Nexus user. */
export function cockpitFetch(path) {
  return fetch(cockpitUrl(path), { headers: nexusAuthHeaders() });
}
