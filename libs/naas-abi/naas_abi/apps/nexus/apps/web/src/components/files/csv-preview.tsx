'use client';

import { useMemo } from 'react';
import { parseDelimitedText } from './parse-delimited-text';

type CsvPreviewProps = {
  content: string;
  fileName?: string | null;
};

export function CsvPreview({ content, fileName }: CsvPreviewProps) {
  const table = useMemo(() => {
    const lower = (fileName || '').toLowerCase();
    const delimiter = lower.endsWith('.tsv') ? '\t' : undefined;
    return parseDelimitedText(content, { delimiter });
  }, [content, fileName]);

  if (table.headers.length === 0 && table.rows.length === 0) {
    return <div className="files-browse-preview-status">Empty file</div>;
  }

  return (
    <div className="files-browse-preview-csv">
      <div className="files-browse-preview-csv-scroll">
        <table>
          <thead>
            <tr>
              {table.headers.map((header, index) => (
                <th key={`h-${index}`}>{header || `Column ${index + 1}`}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={`r-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <td key={`c-${rowIndex}-${cellIndex}`}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.truncated && (
        <p className="files-browse-preview-csv-note">
          Showing first {table.rows.length} of {table.totalRows} rows
        </p>
      )}
    </div>
  );
}
