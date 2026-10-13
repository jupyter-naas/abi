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
  workspaces: string;
};

export type UsersExportFormat = 'csv' | 'xlsx';

const HEADER = ['Name', 'Email', 'Role', 'Workspaces'] as const;
const COLS = ['A', 'B', 'C', 'D'] as const;

/** One row per user. Workspaces are joined with "; " so Excel keeps them in one cell. */
export function usersToCsv(rows: UsersExportRow[]): string {
  const header = HEADER.map(escapeCsvField).join(',');
  const body = rows.map((row) =>
    [row.name, row.email, row.role, row.workspaces]
      .map(escapeCsvField)
      .join(',')
  );
  return [header, ...body].join('\r\n');
}

function xmlCell(col: string, row: number, value: string): string {
  return `<c r="${col}${row}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(value)}</t></is></c>`;
}

function xmlRow(row: number, values: readonly string[]): string {
  return `<row r="${row}">${values
    .map((value, index) => xmlCell(COLS[index], row, value))
    .join('')}</row>`;
}

function usersSheetXml(rows: UsersExportRow[]): string {
  const data = [
    xmlRow(1, HEADER),
    ...rows.map((row, index) =>
      xmlRow(index + 2, [row.name, row.email, row.role, row.workspaces])
    ),
  ].join('');
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<cols>' +
    '<col min="1" max="1" width="24" customWidth="1"/>' +
    '<col min="2" max="2" width="32" customWidth="1"/>' +
    '<col min="3" max="3" width="12" customWidth="1"/>' +
    '<col min="4" max="4" width="48" customWidth="1"/>' +
    '</cols>' +
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

/** Office Open XML workbook. One Users sheet. */
export function usersToXlsx(rows: UsersExportRow[]): Uint8Array {
  return zipStore([
    {
      name: '[Content_Types].xml',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
          '<Default Extension="xml" ContentType="application/xml"/>' +
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
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
          '<sheets><sheet name="Users" sheetId="1" r:id="rId1"/></sheets>' +
          '</workbook>'
      ),
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: xmlBytes(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>' +
          '</Relationships>'
      ),
    },
    {
      name: 'xl/worksheets/sheet1.xml',
      data: xmlBytes(usersSheetXml(rows)),
    },
  ]);
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

export function downloadUsersExport(
  rows: UsersExportRow[],
  format: UsersExportFormat,
  basename: string
): void {
  if (format === 'csv') {
    const bom = String.fromCharCode(0xfeff);
    triggerDownload(
      `${basename}.csv`,
      new Blob([bom + usersToCsv(rows)], { type: 'text/csv;charset=utf-8;' })
    );
    return;
  }
  const xlsx = usersToXlsx(rows);
  const xlsxBuffer = xlsx.buffer.slice(
    xlsx.byteOffset,
    xlsx.byteOffset + xlsx.byteLength
  ) as ArrayBuffer;
  triggerDownload(
    `${basename}.xlsx`,
    new Blob([xlsxBuffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
  );
}
