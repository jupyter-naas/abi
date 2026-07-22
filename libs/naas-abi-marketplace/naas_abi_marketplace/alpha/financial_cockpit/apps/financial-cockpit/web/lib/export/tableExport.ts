import type { DataTableColumn } from '@/components/dashboard/DataTable';
import type { CsvEncoding, CsvExportSettings } from '@/lib/theme/exportFormat';

export type TableExportFormat = 'csv' | 'xlsx';

function formatNumberForExport(value: number, decimal: string): string {
  const text = String(value);
  if (decimal === ',') {
    return text.replace('.', ',');
  }
  return text;
}

export function formatExportCellValue(
  value: unknown,
  column: DataTableColumn,
  csvSettings: CsvExportSettings,
): string | number {
  if (value === null || value === undefined || value === '') {
    return '';
  }

  if (typeof value === 'number') {
    if (column.valueStyle === 'currency' || column.align === 'right') {
      return formatNumberForExport(value, csvSettings.decimal);
    }
    return value;
  }

  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }

  return String(value);
}

function escapeCsvField(value: string, separator: string): string {
  if (value.includes(separator) || value.includes('"') || value.includes('\n') || value.includes('\r')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function encodeIso88591(text: string): Uint8Array {
  const bytes = new Uint8Array(text.length);
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    bytes[index] = code <= 0xff ? code : 0x3f;
  }
  return bytes;
}

function encodeCsvBytes(text: string, encoding: CsvEncoding): Uint8Array {
  if (encoding === 'iso-8859-1') {
    return encodeIso88591(text);
  }

  const utf8 = new TextEncoder().encode(text);
  if (encoding === 'utf-8-bom') {
    const withBom = new Uint8Array(utf8.length + 3);
    withBom.set([0xef, 0xbb, 0xbf], 0);
    withBom.set(utf8, 3);
    return withBom;
  }

  return utf8;
}

export function buildCsvContent(
  records: Record<string, unknown>[],
  columns: DataTableColumn[],
  csvSettings: CsvExportSettings,
): string {
  const separator = csvSettings.separator;
  const header = columns.map((column) => escapeCsvField(column.label, separator)).join(separator);
  const lines = records.map((record) =>
    columns
      .map((column) => {
        const raw = formatExportCellValue(record[column.key], column, csvSettings);
        return escapeCsvField(String(raw), separator);
      })
      .join(separator),
  );

  return [header, ...lines].join('\r\n');
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportTableToCsv(
  records: Record<string, unknown>[],
  columns: DataTableColumn[],
  csvSettings: CsvExportSettings,
  fileName: string,
) {
  const content = buildCsvContent(records, columns, csvSettings);
  const bytes = encodeCsvBytes(content, csvSettings.encoding);
  const mimeType =
    csvSettings.encoding === 'iso-8859-1' ? 'text/csv;charset=iso-8859-1' : 'text/csv;charset=utf-8';
  downloadBlob(new Blob([Uint8Array.from(bytes)], { type: mimeType }), `${fileName}.csv`);
}

export async function exportTableToExcel(
  records: Record<string, unknown>[],
  columns: DataTableColumn[],
  csvSettings: CsvExportSettings,
  fileName: string,
) {
  const XLSX = await import('xlsx');
  const rows = records.map((record) =>
    Object.fromEntries(
      columns.map((column) => [
        column.label,
        formatExportCellValue(record[column.key], column, csvSettings),
      ]),
    ),
  );

  const worksheet = XLSX.utils.json_to_sheet(rows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Données');
  XLSX.writeFile(workbook, `${fileName}.xlsx`);
}

export async function exportTableData(
  format: TableExportFormat,
  records: Record<string, unknown>[],
  columns: DataTableColumn[],
  csvSettings: CsvExportSettings,
  fileName: string,
) {
  if (format === 'csv') {
    exportTableToCsv(records, columns, csvSettings, fileName);
    return;
  }

  await exportTableToExcel(records, columns, csvSettings, fileName);
}
