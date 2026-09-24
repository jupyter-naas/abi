/** Minimal RFC4180-ish CSV/TSV parser for Files preview. No deps. */

export type DelimitedTable = {
  headers: string[];
  rows: string[][];
  truncated: boolean;
  totalRows: number;
};

const MAX_PREVIEW_ROWS = 500;

function detectDelimiter(sample: string): string {
  const firstLine = sample.split(/\r?\n/, 1)[0] ?? '';
  const commas = (firstLine.match(/,/g) || []).length;
  const tabs = (firstLine.match(/\t/g) || []).length;
  const semis = (firstLine.match(/;/g) || []).length;
  if (tabs > commas && tabs >= semis) return '\t';
  if (semis > commas) return ';';
  return ',';
}

function parseLine(line: string, delimiter: string): string[] {
  const cells: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === delimiter) {
      cells.push(current);
      current = '';
      continue;
    }
    current += ch;
  }
  cells.push(current);
  return cells;
}

export function parseDelimitedText(
  text: string,
  options?: { delimiter?: string; maxRows?: number },
): DelimitedTable {
  const maxRows = options?.maxRows ?? MAX_PREVIEW_ROWS;
  const normalized = text.replace(/^\uFEFF/, '');
  const lines = normalized.split(/\r?\n/).filter((line, index, all) => {
    if (line.length > 0) return true;
    // Keep empty lines that are not trailing.
    return index < all.length - 1;
  });

  if (lines.length === 0) {
    return { headers: [], rows: [], truncated: false, totalRows: 0 };
  }

  const delimiter = options?.delimiter ?? detectDelimiter(lines[0] ?? '');
  const parsed = lines.map((line) => parseLine(line, delimiter));
  const width = Math.max(...parsed.map((row) => row.length), 0);
  const padded = parsed.map((row) => {
    if (row.length >= width) return row;
    return [...row, ...Array(width - row.length).fill('')];
  });

  const headers = padded[0] ?? [];
  const body = padded.slice(1);
  const truncated = body.length > maxRows;

  return {
    headers,
    rows: truncated ? body.slice(0, maxRows) : body,
    truncated,
    totalRows: body.length,
  };
}
