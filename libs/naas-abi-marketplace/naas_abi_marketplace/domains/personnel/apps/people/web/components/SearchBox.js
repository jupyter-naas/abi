/** The search field, with an autocomplete list. Used by the home page and the topbar. */

import { fetchSuggestions } from "../lib/api.js";
import { avatarHtml, escapeHtml, ICONS } from "../lib/dom.js";
import { go, profileHref, searchHref } from "../lib/routes.js";

export function searchBoxHtml(config, { value = "", autofocus = false } = {}) {
  const placeholder = escapeHtml(config.brand?.description || "Search people");
  return `
    <form class="search" role="search" autocomplete="off">
      <div class="search-field">
        ${ICONS.search}
        <input
          class="search-input"
          type="search"
          name="q"
          value="${escapeHtml(value)}"
          placeholder="${placeholder}"
          aria-label="${placeholder}"
          ${autofocus ? "autofocus" : ""}
        />
      </div>
      <ul class="suggestions" role="listbox" hidden></ul>
    </form>`;
}

export function wireSearch(root, config) {
  const form = root.querySelector(".search");
  if (!form) return;
  const input = form.querySelector(".search-input");
  const list = form.querySelector(".suggestions");
  const minChars = config.search?.min_autocomplete_chars ?? 2;
  let items = [];
  let active = -1;
  let requestId = 0;

  function close() {
    list.hidden = true;
    list.innerHTML = "";
    items = [];
    active = -1;
  }

  function render() {
    list.innerHTML = items
      .map(
        (person, index) => `
        <li class="suggestion" role="option" data-slug="${escapeHtml(person.slug)}"
            aria-selected="${index === active}">
          ${avatarHtml(person, "sm")}
          <span>
            <span class="suggestion-name">${escapeHtml(person.full_name)}</span><br />
            <span class="suggestion-headline">${escapeHtml(person.headline || "")}</span>
          </span>
        </li>`,
      )
      .join("");
    list.hidden = items.length === 0;
  }

  input.addEventListener("input", async () => {
    const value = input.value.trim();
    if (value.length < minChars) return close();
    const id = ++requestId;
    try {
      const payload = await fetchSuggestions(value);
      // A slower earlier request must not overwrite a newer answer.
      if (id !== requestId) return;
      items = payload.suggestions || [];
      active = -1;
      render();
    } catch {
      close();
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") return close();
    if (!items.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      render();
    }
    if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      go(profileHref(config, items[active].slug));
      close();
    }
  });

  list.addEventListener("mousedown", (event) => {
    const option = event.target.closest(".suggestion");
    if (!option) return;
    event.preventDefault();
    go(profileHref(config, option.dataset.slug));
    close();
  });

  // focusout, not a document-wide click listener: one listener per field, and it
  // goes away with the field instead of piling up on every render.
  form.addEventListener("focusout", () => {
    window.setTimeout(() => {
      if (!form.contains(document.activeElement)) close();
    }, 0);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    close();
    go(searchHref(config, { query: input.value.trim() }));
  });
}
