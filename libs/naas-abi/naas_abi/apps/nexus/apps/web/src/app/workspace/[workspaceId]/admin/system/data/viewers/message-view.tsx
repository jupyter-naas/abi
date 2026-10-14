'use client';

/** A bus message: where it went, its headers, then its payload. */
import { absoluteTime, formatCount } from '../data-model';

export function MessageView({
  subject,
  headers,
  sequence,
  published_at,
}: {
  subject?: string;
  headers?: Record<string, string>;
  sequence?: number;
  published_at?: string;
}) {
  const entries = Object.entries(headers ?? {});
  return (
    <div className="message">
      <dl className="message-facts">
        {subject && (
          <div>
            <dt>Subject</dt>
            <dd className="data-mono">{subject}</dd>
          </div>
        )}
        {sequence !== undefined && (
          <div>
            <dt>Sequence</dt>
            <dd className="data-mono">{formatCount(sequence)}</dd>
          </div>
        )}
        {published_at && (
          <div>
            <dt>Published</dt>
            <dd>{absoluteTime(published_at)}</dd>
          </div>
        )}
      </dl>
      {entries.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Headers</h4>
          <table className="data-kv">
            <tbody>
              {entries.map(([k, v]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td className="data-mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
