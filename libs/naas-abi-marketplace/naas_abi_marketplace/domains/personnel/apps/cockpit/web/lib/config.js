const CONFIG_ENDPOINT = "/api/personnel-cockpit/config";

let cachedConfig = null;

export async function loadAppConfig() {
  if (cachedConfig) return cachedConfig;
  const response = await fetch(CONFIG_ENDPOINT);
  if (!response.ok) throw new Error(`config → ${response.status}`);
  cachedConfig = await response.json();
  return cachedConfig;
}

export function pageMaps(config) {
  const pages = config.app.pages || [];
  return {
    pages,
    byId: Object.fromEntries(pages.map((page) => [page.page_id, page])),
    byUrl: Object.fromEntries(pages.map((page) => [page.url, page])),
  };
}

export function applyTheme(config) {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(config.theme?.css_variables || {})) {
    if (value != null) root.style.setProperty(`--${name}`, String(value));
  }
}

export function applyBrand(config) {
  const brand = config.brand;
  document.title = brand.name;
  document.querySelector(".brand-mark").textContent = brand.mark;
  document.querySelector(".brand-text strong").textContent = brand.short_name;

  if (brand.favicon_src) {
    document.querySelectorAll('link[rel~="icon"]').forEach((link) => link.remove());
    const link = document.createElement("link");
    link.rel = "icon";
    link.href = brand.favicon_src;
    document.head.appendChild(link);
  }
  if (brand.font_stylesheet_url) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = brand.font_stylesheet_url;
    document.head.appendChild(link);
  }
}

export function renderConfiguredPages(config) {
  const pages = config.app.pages || [];
  const nav = document.getElementById("nav");
  const main = document.getElementById("pages");
  nav.innerHTML = pages
    .map(
      (page) => `<button data-page="${page.page_id}" title="${page.label}">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="none" stroke="currentColor" stroke-width="1.75"
            stroke-linecap="square" d="${page.icon_path || ""}" />
        </svg>
        <span class="nav-label">${page.label}</span>
      </button>`
    )
    .join("");
  main.innerHTML = pages
    .map((page) => `<section id="page-${page.page_id}" class="page"></section>`)
    .join("");
}
