import { Fragment } from 'react';

/** One character as it is matched: lowercase, without its accent ("É" → "e"). */
function fold(char: string): string {
  return char.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().charAt(0) || char;
}

/**
 * Where the query's words occur in ``text``, as ``[start, end)`` ranges, merged.
 * Case and accents are ignored ("credit" finds "Crédit"); words of one letter are
 * left out, they would light up half the text.
 */
export function highlightRanges(text: string, query: string): [number, number][] {
  const words = query.split(/\s+/).map(word => Array.from(word).map(fold).join('')).filter(word => word.length > 1);
  if (!text || !words.length) return [];
  // One folded character per UTF-16 unit of the text, so indexes line up.
  const folded = Array.from(text, char => fold(char).padEnd(char.length, ' ')).join('');
  const ranges: [number, number][] = [];
  for (const word of words) {
    for (let at = folded.indexOf(word); at !== -1; at = folded.indexOf(word, at + 1)) {
      ranges.push([at, at + word.length]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else merged.push([...range]);
  }
  return merged;
}

/** ``text`` with the search's words on a yellow background. */
export function Highlight({ text, query }: { text: string | null | undefined; query?: string | null }) {
  if (!text) return null;
  const ranges = query ? highlightRanges(text, query) : [];
  if (!ranges.length) return <>{text}</>;
  const parts: React.ReactNode[] = [];
  let at = 0;
  ranges.forEach(([start, end], i) => {
    if (start > at) parts.push(<Fragment key={`t${i}`}>{text.slice(at, start)}</Fragment>);
    parts.push(
      <mark key={`m${i}`} className="rounded-sm bg-yellow-200 text-inherit dark:bg-yellow-500/40">
        {text.slice(start, end)}
      </mark>,
    );
    at = end;
  });
  if (at < text.length) parts.push(<Fragment key="end">{text.slice(at)}</Fragment>);
  return <>{parts}</>;
}
