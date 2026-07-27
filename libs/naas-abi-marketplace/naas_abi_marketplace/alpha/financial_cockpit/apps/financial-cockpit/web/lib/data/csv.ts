/** Parse a semicolon-separated CSV with a header row into plain string records. */
export function parseSemicolonCsv(content: string): Record<string, string>[] {
  const lines = content.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length === 0) {
    return [];
  }

  const headers = splitCsvLine(lines[0]);
  const rows: Record<string, string>[] = [];

  for (let index = 1; index < lines.length; index += 1) {
    const values = splitCsvLine(lines[index]);
    if (values.every((value) => !value.trim())) {
      continue;
    }
    const record: Record<string, string> = {};
    headers.forEach((header, columnIndex) => {
      record[header] = values[columnIndex]?.trim() ?? '';
    });
    rows.push(record);
  }

  return rows;
}

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      if (inQuotes && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === ';' && !inQuotes) {
      values.push(current);
      current = '';
      continue;
    }
    current += char;
  }

  values.push(current);
  return values;
}
