/**
 * A row of tabs that never wraps or scrolls: what does not fit goes behind an
 * "N more" tab, whose menu lists the rest (as in a Notion database view).
 */

/**
 * Which tabs stay in the row.
 *
 * ``widths`` are the tabs' widths in order (gap included), ``available`` the
 * row's width and ``moreWidth`` the "N more" tab's. The tabs are kept in order
 * while they fit beside the "N more" tab, and the selected one (``current``,
 * -1 for none) is always kept: when it would be hidden it takes the place of
 * the last tabs that fit. Returns the indexes kept, in order.
 */
export function fitTabs(widths, available, moreWidth, current = -1) {
  const total = widths.reduce((sum, width) => sum + width, 0);
  if (total <= available) return widths.map((_, index) => index);

  const room = available - moreWidth;
  const kept = [];
  let used = 0;
  for (const [index, width] of widths.entries()) {
    if (used + width > room) break;
    kept.push(index);
    used += width;
  }
  if (current < 0 || kept.includes(current)) return kept;

  used += widths[current];
  while (kept.length && used > room) used -= widths[kept.pop()];
  return [...kept, current].sort((a, b) => a - b);
}

const MORE_LABEL = (count) => `${count} more`;

/**
 * Lay out ``row`` (a ``.tabs`` element of ``.tab`` links) and keep it laid out
 * as it resizes. The links that do not fit are hidden in the row and listed,
 * as copies, in the "N more" menu.
 */
export function overflowTabs(row) {
  const tabs = [...row.querySelectorAll(":scope > .tab")];
  if (tabs.length < 2) return;

  const more = document.createElement("div");
  more.className = "tab-more";
  more.innerHTML = `
    <button type="button" class="tab tab-more-button" aria-haspopup="true" aria-expanded="false"></button>
    <div class="tab-menu" hidden></div>`;
  row.appendChild(more);
  const button = more.querySelector(".tab-more-button");
  const menu = more.querySelector(".tab-menu");

  const close = () => {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };
  const open = () => {
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
    menu.querySelector("a")?.focus();
  };
  button.addEventListener("click", () => (menu.hidden ? open() : close()));
  more.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !menu.hidden) {
      close();
      button.focus();
    }
  });
  const onOutsideClick = (event) => {
    if (!row.isConnected) {
      document.removeEventListener("click", onOutsideClick);
      return;
    }
    if (!more.contains(event.target)) close();
  };
  document.addEventListener("click", onOutsideClick);

  const layout = () => {
    close();
    for (const tab of tabs) tab.hidden = false;
    more.hidden = false;
    button.textContent = MORE_LABEL(tabs.length);
    const gap = parseFloat(getComputedStyle(row).columnGap) || 0;
    const widths = tabs.map((tab) => tab.offsetWidth + gap);
    const current = tabs.findIndex((tab) => tab.getAttribute("aria-current") === "true");
    const kept = new Set(fitTabs(widths, row.clientWidth, more.offsetWidth + gap, current));

    const hidden = tabs.filter((_, index) => !kept.has(index));
    for (const tab of hidden) tab.hidden = true;
    more.hidden = hidden.length === 0;
    button.textContent = MORE_LABEL(hidden.length);
    menu.replaceChildren(
      ...hidden.map((tab) => {
        const item = tab.cloneNode(true);
        item.hidden = false;
        item.className = "tab-menu-item";
        return item;
      }),
    );
  };

  layout();
  let width = row.clientWidth;
  const observer = new ResizeObserver(() => {
    if (!row.isConnected) {
      observer.disconnect();
      return;
    }
    if (row.clientWidth !== width) {
      width = row.clientWidth;
      layout();
    }
  });
  observer.observe(row);
}
