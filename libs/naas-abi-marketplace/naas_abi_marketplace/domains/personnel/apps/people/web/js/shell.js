/**
 * Boot, route, mount.
 *
 * The shell knows three things: how to read the configuration, how to turn the
 * hash into a page, and where to put what that page returns.
 */

import { searchBoxHtml, wireSearch } from "../components/SearchBox.js";
import { applyBrand, applyTheme, loadAppConfig, logoHtml } from "../lib/config.js";
import { escapeHtml } from "../lib/dom.js";
import { syncContentAlign, watchContentAlign } from "../lib/layout.js";
import { mountPage } from "../lib/registry.js";
import { parseRoute } from "../lib/routes.js";

const view = document.getElementById("view");
const topbar = document.getElementById("topbar");
const footer = document.getElementById("footer");
const scrollMemory = new Map();
let config = null;
let currentHash = null;

/**
 * A portrait or a flag that fails to load is removed rather than left as a
 * broken icon. Capture phase, because error events do not bubble.
 */
document.addEventListener(
  "error",
  (event) => {
    const target = event.target;
    if (target instanceof HTMLImageElement) target.remove();
  },
  true,
);

function renderTopbar(state) {
  if (!state.showTopbarSearch) {
    topbar.hidden = true;
    return;
  }
  topbar.hidden = false;
  document.getElementById("topbar-logo").outerHTML = logoHtml(config).replace(
    'class="brand-logo"',
    'class="brand-logo" id="topbar-logo"',
  );
  document.getElementById("topbar-name").textContent = config.brand?.short_name || "";
  const host = document.getElementById("topbar-search");
  host.innerHTML = searchBoxHtml(config, { value: state.query || "" });
  wireSearch(host, config);
}

function renderFooter() {
  footer.hidden = false;
  document.getElementById("footer-note").textContent =
    `${config.brand?.name || "People"} · built from the personnel graph`;
}

async function render() {
  const route = parseRoute(config);
  if (currentHash) scrollMemory.set(currentHash, window.scrollY);
  currentHash = window.location.hash || "#/";

  let state = { showTopbarSearch: true };
  try {
    state = (await mountPage(route.pageId, view, { config, ...route })) || state;
  } catch (error) {
    view.innerHTML = `<div class="results"><div class="empty-state error-block">
      <h2>Something went wrong</h2><p>${escapeHtml(error.message)}</p></div></div>`;
  }
  renderTopbar(state);
  watchContentAlign();
  renderFooter();
  document.title = state.title || config.brand?.name || "People";
  window.scrollTo(0, scrollMemory.get(currentHash) || 0);
}

// "/" focuses the search field, the way a search page is expected to behave.
document.addEventListener("keydown", (event) => {
  if (event.key !== "/" || event.metaKey || event.ctrlKey) return;
  const active = document.activeElement;
  if (active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)) return;
  const input = document.querySelector(".search-input");
  if (input) {
    event.preventDefault();
    input.focus();
    input.select();
  }
});

window.addEventListener("hashchange", render);
window.addEventListener("resize", syncContentAlign);

(async function start() {
  try {
    config = await loadAppConfig();
  } catch (error) {
    view.innerHTML = `<div class="results"><div class="empty-state error-block">
      <h2>This app is not configured</h2>
      <p>${escapeHtml(error.message)}</p>
      <p>The configuration endpoint did not answer. Is the app's API mounted?</p>
    </div></div>`;
    return;
  }
  applyTheme(config);
  applyBrand(config);
  await render();
})();
