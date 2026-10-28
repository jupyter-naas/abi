'use client';

/** Rows and typed columns (dataset previews and any tabular view). */
import { formatCount } from '../data-model';

function Cell({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') {
    return <span className="grid-null">null</span>;
  }
  if (typeof value === 'number') return <span className="grid-number">{formatCount(value)}</span>;
  if (typeof value === 'boolean') return <span className="grid-boolean">{String(value)}</span>;
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return <span title={text.length > 60 ? text : undefined}>{text}</span>;
}

export function DataGrid({
  columns,
  rows,
  total,
}: {
  columns: { name: string; type?: string }[];
  rows: unknown[][];
  total?: number | null;
}) {
  return (
    <div className="grid">
      <div className="grid-scroll">
        <table className="grid-table">
          <thead>
            <tr>
              <th className="grid-rownum" aria-label="Row" />
              {columns.map((c) => (
                <th key={c.name}>
                  <span className="grid-col-name">{c.name}</span>
                  {c.type && <span className="grid-col-type">{c.type}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td className="grid-rownum">{i + 1}</td>
                {columns.map((c, j) => (
                  <td key={c.name} className={typeof row[j] === 'number' ? 'grid-cell-number' : undefined}>
                    <Cell value={row[j]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="grid-footer">
        {total !== null && total !== undefined && total > rows.length
          ? `First ${formatCount(rows.length)} of ${formatCount(total)} rows`
          : `${formatCount(rows.length)} ${rows.length === 1 ? 'row' : 'rows'}`}
      </p>
    </div>
  );
}
