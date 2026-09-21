import type { ReactNode } from "react";

/** Needle used for matching/highlighting (trim, strip leading @). */
export function searchHighlightNeedle(raw: string): string {
  return raw.trim().replace(/^@+/, "");
}

/**
 * Highlight every case-insensitive occurrence of `needle` in `text`.
 * Returns plain text when there is nothing to highlight.
 */
export function highlightSearchNeedle(text: string, needle: string): ReactNode {
  const hay = text ?? "";
  const q = searchHighlightNeedle(needle);
  if (!q || !hay) return hay || "";

  const hayLower = hay.toLowerCase();
  const qLower = q.toLowerCase();
  const nodes: ReactNode[] = [];
  let start = 0;
  let hit = 0;

  while (start < hay.length) {
    const at = hayLower.indexOf(qLower, start);
    if (at === -1) {
      nodes.push(hay.slice(start));
      break;
    }
    if (at > start) nodes.push(hay.slice(start, at));
    nodes.push(
      <span key={`${at}-${hit}`} className="search-needle-hit">
        {hay.slice(at, at + q.length)}
      </span>,
    );
    hit += 1;
    start = at + q.length;
  }

  if (nodes.length === 1 && typeof nodes[0] === "string") return nodes[0];
  return <>{nodes}</>;
}
