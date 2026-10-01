/**
 * Configuration: fetched once, then applied to the document.
 *
 * Nothing in this app hardcodes a colour, a label or a section. What the server
 * validated in config.yaml is what the page renders.
 */

/**
 * Which API to ask. An instance page declares its own in a meta tag, because
 * two instances of this app can be mounted in one process under two prefixes.
 */
export const API_BASE =
  document.querySelector('meta[name="people-api-base"]')?.content?.replace(/\/$/, "") ||
  "/api/personnel-people";

let cached = null;

export async function loadAppConfig() {
  if (cached) return cached;
  const response = await fetch(`${API_BASE}/config`);
  if (!response.ok) throw new Error(`config → ${response.status}`);
  cached = await response.json();
  return cached;
}

export function applyTheme(config) {
  const root = document.documentElement;
  for (const [name, value] of Object.entries(config.theme?.css_variables || {})) {
    if (value != null) root.style.setProperty(`--${name}`, String(value));
  }
}

const FAVICON_TYPES = {
  svg: "image/svg+xml",
  png: "image/png",
  ico: "image/x-icon",
  gif: "image/gif",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
};

export function applyBrand(config) {
  const brand = config.brand || {};
  document.title = brand.name || "People";

  if (brand.favicon_src) {
    document.querySelectorAll('link[rel~="icon"]').forEach((link) => link.remove());
    const link = document.createElement("link");
    link.rel = "icon";
    link.href = brand.favicon_src;
    const extension = brand.favicon_src.split(".").pop().toLowerCase();
    if (FAVICON_TYPES[extension]) link.type = FAVICON_TYPES[extension];
    document.head.appendChild(link);
  }
  if (brand.font_stylesheet_url) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = brand.font_stylesheet_url;
    document.head.appendChild(link);
  }
}

/**
 * The brand logo, or the configured letter when no logo file is set.
 * Never a hardcoded image: an app with someone else's logo baked in is a fork.
 */
export function logoHtml(config, className = "") {
  const brand = config.brand || {};
  const classes = ["brand-logo", className].filter(Boolean).join(" ");
  if (brand.logo_src) {
    return `<span class="${classes}"><img src="${brand.logo_src}" alt="" /></span>`;
  }
  return `<span class="${classes} is-mark">${brand.mark || "?"}</span>`;
}

export function pageUrl(config, pageId) {
  const page = (config.app?.pages || []).find((item) => item.page_id === pageId);
  return page ? page.url : "";
}
