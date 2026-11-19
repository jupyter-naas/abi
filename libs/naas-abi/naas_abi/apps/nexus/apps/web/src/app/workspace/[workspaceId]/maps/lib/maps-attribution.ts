/**
 * A basemap's attribution, as Leaflet's attribution control may hold it.
 *
 * The control writes attributions as HTML, and a basemap's comes from the
 * API (a workspace's own basemaps included). It is text, with links written
 * exactly `<a href="https://...">label</a>` (what the API accepts): those links
 * are rebuilt, and every other `<` or `>` is escaped, so the attribution never
 * becomes an element of any other kind.
 */

const LINK = /<a href="(https:\/\/[^\s"'<>`]+)">([^<>]*)<\/a>/g;

function escapeMarkup(text: string): string {
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function attributionHtml(raw: string | null | undefined): string {
  if (!raw) return '';
  let html = '';
  let last = 0;
  for (const match of raw.matchAll(LINK)) {
    html += escapeMarkup(raw.slice(last, match.index));
    html += `<a href="${match[1]}" target="_blank" rel="noopener noreferrer">${match[2]}</a>`;
    last = (match.index ?? 0) + match[0].length;
  }
  return html + escapeMarkup(raw.slice(last));
}
