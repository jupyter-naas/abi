/** Align scrollable content with the topbar search field's left edge. */

let alignObserver = null;

export function syncContentAlign() {
  const root = document.documentElement;
  const topbar = document.getElementById("topbar");
  const field = topbar && !topbar.hidden ? topbar.querySelector(".search-field") : null;
  if (!field) {
    root.style.removeProperty("--content-inset-left");
    return;
  }
  root.style.setProperty("--content-inset-left", `${Math.round(field.getBoundingClientRect().left)}px`);
}

export function watchContentAlign() {
  if (alignObserver) {
    alignObserver.disconnect();
    alignObserver = null;
  }
  const topbar = document.getElementById("topbar");
  if (!topbar || topbar.hidden) {
    syncContentAlign();
    return;
  }
  const nodes = [
    topbar,
    document.getElementById("topbar-brand"),
    document.getElementById("topbar-search"),
  ].filter(Boolean);
  alignObserver = new ResizeObserver(() => syncContentAlign());
  for (const node of nodes) alignObserver.observe(node);
  syncContentAlign();
  requestAnimationFrame(syncContentAlign);
}
