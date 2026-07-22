export type SpreadsheetSheet = {
  name: string;
  headers: string[];
  rows: Record<string, string>[];
};

function cellToString(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (value instanceof Date) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return String(value).trim();
}

function sheetFromJson(name: string, json: Record<string, unknown>[]): SpreadsheetSheet {
  const headers = json.length > 0 ? Object.keys(json[0]) : [];
  const rows = json.map((row) =>
    Object.fromEntries(Object.entries(row).map(([key, value]) => [key, cellToString(value)])),
  );
  return { name, headers, rows };
}

export async function readSpreadsheetFile(file: File): Promise<SpreadsheetSheet[]> {
  const XLSX = await import('xlsx');
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array', cellDates: true, raw: false });

  return workbook.SheetNames.map((name) => {
    const worksheet = workbook.Sheets[name];
    const json = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, { defval: '' });
    return sheetFromJson(name, json);
  }).filter((sheet) => sheet.headers.length > 0 || sheet.rows.length > 0);
}

export const SPREADSHEET_ACCEPT =
  '.csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
