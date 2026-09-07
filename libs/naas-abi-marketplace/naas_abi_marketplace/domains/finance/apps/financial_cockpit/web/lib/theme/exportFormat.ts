export type CsvEncoding = 'iso-8859-1' | 'utf-8' | 'utf-8-bom';

export type CsvExportSettings = {
  encoding: CsvEncoding;
  separator: string;
  decimal: string;
};

export type ExportFormatSettings = {
  csv: CsvExportSettings;
};

export const CSV_ENCODING_OPTIONS = [
  { id: 'iso-8859-1', label: 'ISO-8859-1 (Latin-1, France)' },
  { id: 'utf-8-bom', label: 'UTF-8 avec BOM (Excel)' },
  { id: 'utf-8', label: 'UTF-8' },
] as const satisfies ReadonlyArray<{ id: CsvEncoding; label: string }>;

export const CSV_SEPARATOR_OPTIONS = [
  { id: ';', label: 'Point-virgule (;)' },
  { id: ',', label: 'Virgule (,)' },
  { id: '\t', label: 'Tabulation' },
] as const;

export const CSV_DECIMAL_OPTIONS = [
  { id: ',', label: 'Virgule (,)' },
  { id: '.', label: 'Point (.)' },
] as const;

/** French CSV defaults aligned with Pennylane exports (sep `;`, decimal `,`, ISO-8859-1). */
export const DEFAULT_EXPORT_FORMAT: ExportFormatSettings = {
  csv: {
    encoding: 'iso-8859-1',
    separator: ';',
    decimal: ',',
  },
};

export function mergeExportFormat(
  parsed?: Partial<ExportFormatSettings> | null,
): ExportFormatSettings {
  const defaults = DEFAULT_EXPORT_FORMAT;
  const csv = parsed?.csv;

  const encoding = CSV_ENCODING_OPTIONS.some((option) => option.id === csv?.encoding)
    ? (csv!.encoding as CsvEncoding)
    : defaults.csv.encoding;

  const separator =
    CSV_SEPARATOR_OPTIONS.find((option) => option.id === csv?.separator)?.id ??
    defaults.csv.separator;

  const decimal =
    CSV_DECIMAL_OPTIONS.find((option) => option.id === csv?.decimal)?.id ??
    defaults.csv.decimal;

  return {
    csv: {
      encoding,
      separator,
      decimal,
    },
  };
}
