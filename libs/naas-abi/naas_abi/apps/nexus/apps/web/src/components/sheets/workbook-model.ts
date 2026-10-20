/** The persisted workbook model, shared by the grid and SheetsAgent. */
export type Cell = string | number | null;
export type Workbook = { title: string; sheets: { name: string; rows: Cell[][]; column_widths?: Record<string, number>; row_heights?: Record<string, number> }[] };
export type Position = { row: number; col: number };
const block = /(<script\b[^>]*\btype=["']application\/vnd\.nexus\.sheet\+json["'][^>]*>)([\s\S]*?)(<\/script\s*>)/i;
export function readWorkbook(html: string): Workbook | null {
  try {
    const model = JSON.parse(html.match(block)?.[2] ?? 'null');
    if (!model || !Array.isArray(model.sheets) || !model.sheets.length) return null;
    if (!model.sheets.every((s: Workbook['sheets'][number]) => typeof s.name === 'string' && Array.isArray(s.rows) && s.rows.every(r => Array.isArray(r) && r.every(c => c === null || typeof c === 'string' || typeof c === 'number')))) return null;
    return model;
  } catch { return null; }
}
export function writeWorkbook(html: string, model: Workbook): string {
  // Escape '<' so a cell containing </script> cannot terminate the data block.
  const json = JSON.stringify(model, null, 2).replace(/</g, '\\u003c');
  return html.replace(block, (_, open, _old, close) => `${open}\n${json}\n${close}`);
}
export function columnLabel(index: number): string {
  let label = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) label = String.fromCharCode(65 + (n - 1) % 26) + label;
  return label;
}
export function address(p: Position): string { return `${columnLabel(p.col)}${p.row + 1}`; }
export function parseAddress(value: string): Position | null {
  const match = /^\$?([A-Z]+)\$?([1-9]\d*)$/i.exec(value.trim());
  if (!match) return null;
  let col = 0;
  for (const c of match[1].toUpperCase()) col = col * 26 + c.charCodeAt(0) - 64;
  const row = Number(match[2]);
  return col <= 16384 && row <= 1048576 ? { row: row - 1, col: col - 1 } : null;
}
export function cellInput(text: string): Cell {
  if (text === '') return null;
  // Preserve identifiers, leading zeroes and explicit text.
  if (/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(text) && Number.isFinite(Number(text))) return Number(text);
  return text;
}
export function patchCells(model: Workbook, sheet: number, start: Position, values: Cell[][]): Workbook {
  const next = structuredClone(model);
  const rows = next.sheets[sheet].rows;
  values.forEach((line, r) => {
    while (rows.length <= start.row + r) rows.push([]);
    line.forEach((value, c) => {
      const row = rows[start.row + r];
      while (row.length <= start.col + c) row.push(null);
      row[start.col + c] = value;
    });
  });
  return next;
}
/** Parse quoted TSV (Excel/Sheets clipboard), including embedded newlines. */
export function parseClipboard(text: string): Cell[][] {
  const rows: Cell[][] = []; let row: Cell[] = []; let value = ''; let quoted = false;
  const input = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  for (let i = 0; i < input.length; i++) {
    const c = input[i];
    if (c === '"' && (quoted || value === '')) {
      if (quoted && input[i + 1] === '"') { value += '"'; i++; } else quoted = !quoted;
    } else if (!quoted && (c === '\t' || c === '\n')) {
      row.push(cellInput(value)); value = '';
      if (c === '\n') { rows.push(row); row = []; }
    } else value += c;
  }
  if (value || row.length || !rows.length) { row.push(cellInput(value)); rows.push(row); }
  return rows;
}
export function copyRange(model: Workbook, sheet: number, a: Position, b: Position): string {
  const lines: string[] = [];
  for (let r = Math.min(a.row, b.row); r <= Math.max(a.row, b.row); r++) {
    const cells: string[] = [];
    for (let c = Math.min(a.col, b.col); c <= Math.max(a.col, b.col); c++) {
      const value = String(model.sheets[sheet].rows[r]?.[c] ?? '');
      cells.push(/[\t\n\r"]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value);
    }
    lines.push(cells.join('\t'));
  }
  return lines.join('\n');
}
export function uniqueSheetName(model: Workbook): string {
  let i = 1;
  while (model.sheets.some(s => s.name.toLowerCase() === `sheet${i}`)) i++;
  return `Sheet${i}`;
}
export function renameSheet(model: Workbook, index: number, name: string): Workbook {
  name = name.trim();
  if (!name || name.length > 31 || /[\\/?*\[\]:]/.test(name) || name.startsWith("'") || name.endsWith("'")) throw new Error('Use 1–31 characters without : \\ / ? * [ ] or an apostrophe at either end.');
  if (model.sheets.some((s, i) => i !== index && s.name.toLowerCase() === name.toLowerCase())) throw new Error('A sheet with that name already exists.');
  const next = structuredClone(model);
  const old = model.sheets[index].name;
  // Only reference tokens outside Excel string literals; never alter cell text.
  for (const sheet of next.sheets) for (const row of sheet.rows) for (let c = 0; c < row.length; c++) {
    const value = row[c]; if (typeof value !== 'string' || !value.startsWith('=')) continue;
    row[c] = value.split(/("(?:[^"]|"")*")/g).map((part, i) => i % 2 ? part : part.replace(/('(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!/g, (token, label: string) => {
      const decoded = label.startsWith("'") ? label.slice(1, -1).replace(/''/g, "'") : label;
      return decoded.toLowerCase() === old.toLowerCase() ? `'${name.replace(/'/g, "''")}'!` : token;
    })).join('');
  }
  next.sheets[index].name = name;
  return next;
}
