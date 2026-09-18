/** Small rendering helpers shared by the pages. */

export const ICONS = {
  search:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  place:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true" width="14" height="14"><path d="M12 21s7-5.7 7-11a7 7 0 1 0-14 0c0 5.3 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  link:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true" width="16" height="16"><path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/></svg>',
};

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );
}

/** Same folding as the server: "Cédric" and "cedric" must be one word. */
export function fold(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/**
 * Mark the words the query matched, in text the reader is about to see.
 *
 * Folding is done per character so the marks land on the original string, with
 * its accents and capitals intact.
 */
export function highlight(text, tokens, tag = "mark") {
  const raw = String(text ?? "");
  if (!tokens?.length || !raw) return escapeHtml(raw);
  const folded = fold(raw);
  if (folded.length !== raw.length) return escapeHtml(raw);

  const ranges = [];
  for (const match of folded.matchAll(/[a-z0-9+]+/g)) {
    const token = tokens.find((candidate) => match[0].startsWith(candidate));
    if (token) ranges.push([match.index, match.index + token.length]);
  }
  if (!ranges.length) return escapeHtml(raw);

  let out = "";
  let cursor = 0;
  for (const [start, end] of ranges) {
    out += escapeHtml(raw.slice(cursor, start));
    out += `<${tag}>${escapeHtml(raw.slice(start, end))}</${tag}>`;
    cursor = end;
  }
  return out + escapeHtml(raw.slice(cursor));
}

export function initials(name) {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  const last = parts.length > 1 ? parts[parts.length - 1] : "";
  return ((parts[0][0] || "") + (last[0] || "")).toUpperCase();
}

/**
 * A portrait, or the person's initials.
 *
 * The initials are rendered underneath rather than swapped in on error, so a
 * portrait that 404s degrades to something readable instead of a broken icon.
 */
export function avatarHtml(person, size = "sm") {
  const label = escapeHtml(person.full_name || "");
  const fallback = escapeHtml(initials(person.full_name));
  const image = person.photo_url
    ? `<img src="${escapeHtml(person.photo_url)}" alt="" loading="lazy" />`
    : "";
  return `<span class="avatar avatar-${size}" role="img" aria-label="${label}">${fallback}${image}</span>`;
}

/**
 * Country flags come from a CDN; without one the line simply has no flag.
 * Removal on error is handled once, in shell.js, rather than with an inline
 * handler that a content-security policy would block.
 */
export function flagHtml(countryCode) {
  if (!countryCode || countryCode.length !== 2) return "";
  const code = countryCode.toLowerCase();
  return `<img class="result-flag" src="https://flagcdn.com/32x24/${code}.png" alt="" loading="lazy" />`;
}

export function yearOf(isoDate) {
  return isoDate ? String(isoDate).slice(0, 4) : "";
}

/**
 * A period as the source stated it: years, or the source's own duration label.
 * "Present" only ever means an open end, never a guess.
 */
export function periodText(item, { presentLabel = "Present" } = {}) {
  const start = yearOf(item.start);
  const end = yearOf(item.end);
  const span = start ? `${start} – ${end || presentLabel}` : end || "";
  return [span, item.duration].filter(Boolean).join(" · ");
}
