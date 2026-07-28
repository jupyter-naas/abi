'use client';

import { useTheme } from '@/lib/theme/ThemeProvider';
import { fieldInput } from '@/lib/ariaStyles';
import {
  CSV_DECIMAL_OPTIONS,
  CSV_ENCODING_OPTIONS,
  CSV_SEPARATOR_OPTIONS,
  type CsvExportSettings,
} from '@/lib/theme/exportFormat';

function ExportField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { id: string; label: string }[];
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs">
      <span className="text-[var(--text-muted)]">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${fieldInput} !min-h-9 py-1.5`}
      >
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ExportFormatEditor() {
  const { colors, updateExportFormat } = useTheme();
  const csv = colors.exportFormat.csv;

  function patchCsv(partial: Partial<CsvExportSettings>) {
    updateExportFormat({ csv: { ...csv, ...partial } });
  }

  return (
    <div className="border border-[var(--border)] px-4 py-4">
      <p className="mb-4 text-sm text-[var(--text-muted)]">
        Paramètres par défaut pour les exports CSV du portail (séparateur, décimales, encodage).
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <ExportField
          label="Encodage"
          value={csv.encoding}
          onChange={(value) => patchCsv({ encoding: value as CsvExportSettings['encoding'] })}
          options={CSV_ENCODING_OPTIONS}
        />
        <ExportField
          label="Séparateur"
          value={csv.separator}
          onChange={(value) => patchCsv({ separator: value })}
          options={CSV_SEPARATOR_OPTIONS}
        />
        <ExportField
          label="Décimale"
          value={csv.decimal}
          onChange={(value) => patchCsv({ decimal: value })}
          options={CSV_DECIMAL_OPTIONS}
        />
      </div>
    </div>
  );
}
