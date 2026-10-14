/** Escape one field per RFC 4180. */
function escapeCsvField(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export type UsersExportRow = {
  name: string;
  email: string;
  role: string;
  /** Joined with "; ". Workspaces for an organization, organizations for the platform. */
  groups: string;
};

export type UsersExportFormat = 'csv' | 'xlsx';

function header(groupsHeader: string): string[] {
  return ['Name', 'Email', 'Role', groupsHeader];
}

function userValues(row: UsersExportRow): string[] {
  return [row.name, row.email, row.role, row.groups];
}

const USERS_COLUMN_WIDTHS = [24, 32, 12, 48];

/** Any table as CSV (RFC 4180). */
export function tableToCsv(headers: readonly string[], rows: readonly (readonly string[])[]): string {
  return [headers, ...rows].map((values) => values.map(escapeCsvField).join(',')).join('\r\n');
}

/** One row per user. Groups are joined with "; " so Excel keeps them in one cell. */
export function usersToCsv(rows: UsersExportRow[], groupsHeader = 'Workspaces'): string {
  return tableToCsv(header(groupsHeader), rows.map(userValues));
}

/** Spreadsheet column letters: 0 → A, 25 → Z, 26 → AA. */
export function columnLetter(index: number): string {
  let letters = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    letters = String.fromCharCode(65 + ((n - 1) % 26)) + letters;
  }
  return letters;
}

function xmlCell(col: string, row: number, value: string): string {
  return `<c r="${col}${row}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`;
}

function xmlRow(row: number, values: readonly string[]): string {
  return `<row r="${row}">${values
    .map((value, index) => xmlCell(columnLetter(index), row, value))
    .join('')}</row>`;
}

function sheetXml(
  headers: readonly string[],
  rows: readonly (readonly string[])[],
  widths?: readonly number[]
): string {
  const data = [xmlRow(1, headers), ...rows.map((values, index) => xmlRow(index + 2, values))].join(
    ''
  );
  const cols = widths?.length
    ? `<cols>${widths
        .map((width, index) => `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`)
        .join('')}</cols>`
    : '';
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    cols +
    `<sheetData>${data}</sheetData>` +
    '</worksheet>'
  );
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let value = i;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[i] = value >>> 0;
  }
  return table;
})();

function crc32(data: Uint8Array): number {
  let value = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    value = CRC_TABLE[(value ^ data[i]) & 0xff] ^ (value >>> 8);
  }
  return (value ^ 0xffffffff) >>> 0;
}

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function u16(value: number): Uint8Array {
  const bytes = new Uint8Array(2);
  new DataView(bytes.buffer).setUint16(0, value, true);
  return bytes;
}

function u32(value: number): Uint8Array {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value, true);
  return bytes;
}

/** Uncompressed ZIP. Excel opens this as a native .xlsx. */
function zipStore(files: { name: string; data: Uint8Array }[]): Uint8Array {
  const encoder = new TextEncoder();
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let offset = 0;
  for (const file of files) {
    const name = encoder.encode(file.name);
    const crc = crc32(file.data);
    const local = concat([
      u32(0x04034b50),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(file.data.length),
      u32(file.data.length),
      u16(name.length),
      u16(0),
      name,
      file.data,
    ]);
    centrals.push(
      concat([
        u32(0x02014b50),
        u16(20),
        u16(20),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(crc),
        u32(file.data.length),
        u32(file.data.length),
        u16(name.length),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(0),
        u32(offset),
        name,
      ])
    );
    locals.push(local);
    offset += local.length;
  }
  const localBlob = concat(locals);
  const centralBlob = concat(centrals);
  return concat([
    localBlob,
    centralBlob,
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(files.length),
    u16(files.length),
    u32(centralBlob.length),
    u32(localBlob.length),
    u16(0),
  ]);
}

function xmlBytes(xml: string): Uint8Array {
  return new TextEncoder().encode(xml);
}

export type WorkbookSheet = {
  name: string;
  headers: readonly string[];
  rows: readonly (readonly string[])[];
  widths?: readonly number[];
};

const XLSX_SHEET_NAME_MAX = 31;

/** Office Open XML workbook, one sheet per entry (names cut to Excel's 31 characters). */
export function workbookToXlsx(sheets: readonly WorkbookSheet[]): Uint8Array {
  const parts = sheets.map((_, index) => index + 1);
  return zipStore([
    {
      name: '[Content_Types].xml',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
          '<Default Extension="xml" ContentType="application/xml"/>' +
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
          parts
            .map(
              (n) =>
                `<Override PartName="/xl/worksheets/sheet${n}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`
            )
            .join('') +
          '</Types>'
      ),
    },
    {
      name: '_rels/.rels',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
          '</Relationships>'
      ),
    },
    {
      name: 'xl/workbook.xml',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
          `<sheets>${sheets
            .map(
              (sheet, index) =>
                `<sheet name="${escapeXml(sheet.name.slice(0, XLSX_SHEET_NAME_MAX))}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`
            )
            .join('')}</sheets>` +
          '</workbook>'
      ),
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          parts
            .map(
              (n) =>
                `<Relationship Id="rId${n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${n}.xml"/>`
            )
            .join('') +
          '</Relationships>'
      ),
    },
    ...sheets.map((sheet, index) => ({
      name: `xl/worksheets/sheet${index + 1}.xml`,
      data: xmlBytes(sheetXml(sheet.headers, sheet.rows, sheet.widths)),
    })),
  ]);
}

/** Office Open XML workbook with one sheet. */
export function tableToXlsx(
  headers: readonly string[],
  rows: readonly (readonly string[])[],
  sheetName = 'Sheet1',
  widths?: readonly number[]
): Uint8Array {
  return workbookToXlsx([{ name: sheetName, headers, rows, widths }]);
}

/** Office Open XML workbook. One Users sheet. */
export function usersToXlsx(rows: UsersExportRow[], groupsHeader = 'Workspaces'): Uint8Array {
  return tableToXlsx(header(groupsHeader), rows.map(userValues), 'Users', USERS_COLUMN_WIDTHS);
}

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadExport(
  format: UsersExportFormat,
  basename: string,
  csv: () => string,
  xlsx: () => Uint8Array
): void {
  if (format === 'csv') {
    const bom = String.fromCharCode(0xfeff);
    triggerDownload(
      `${basename}.csv`,
      new Blob([bom + csv()], { type: 'text/csv;charset=utf-8;' })
    );
    return;
  }
  const bytes = xlsx();
  const xlsxBuffer = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer;
  triggerDownload(
    `${basename}.xlsx`,
    new Blob([xlsxBuffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
  );
}

export function downloadUsersExport(
  rows: UsersExportRow[],
  format: UsersExportFormat,
  basename: string,
  groupsHeader = 'Workspaces'
): void {
  downloadExport(
    format,
    basename,
    () => usersToCsv(rows, groupsHeader),
    () => usersToXlsx(rows, groupsHeader)
  );
}

/** Any table, every column. The sheet is named after the table. */
export function downloadTableExport(
  headers: readonly string[],
  rows: readonly (readonly string[])[],
  format: UsersExportFormat,
  basename: string,
  sheetName: string
): void {
  downloadExport(
    format,
    basename,
    () => tableToCsv(headers, rows),
    () => tableToXlsx(headers, rows, sheetName)
  );
}

function xlsxBlob(bytes: Uint8Array): Blob {
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  return new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}

/** Several tables in one Excel file, one sheet each. */
export function downloadWorkbookExport(sheets: readonly WorkbookSheet[], basename: string): void {
  triggerDownload(`${basename}.xlsx`, xlsxBlob(workbookToXlsx(sheets)));
}

/** Any JSON value as a pretty-printed .json file. */
export function downloadJsonExport(data: unknown, basename: string): void {
  triggerDownload(
    `${basename}.json`,
    new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8;' })
  );
}
