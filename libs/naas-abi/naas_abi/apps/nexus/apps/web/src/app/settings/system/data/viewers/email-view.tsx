'use client';

/** A sent email as a reader shows it. HTML renders in a sandbox with no scripts. */
import { useState } from 'react';
import { absoluteTime } from '../data-model';

function list(value: string[] | string | undefined): string {
  if (!value) return '';
  return Array.isArray(value) ? value.join(', ') : value;
}

export function EmailView({
  from,
  to,
  cc,
  subject,
  text,
  html,
  sent_at,
}: {
  from?: string;
  to?: string[] | string;
  cc?: string[] | string;
  subject?: string;
  text?: string;
  html?: string;
  sent_at?: string;
}) {
  const [mode, setMode] = useState<'html' | 'text'>(html ? 'html' : 'text');
  return (
    <article className="mail">
      <h3 className="mail-subject">{subject || '(no subject)'}</h3>
      <dl className="mail-headers">
        {from && (
          <>
            <dt>From</dt>
            <dd>{from}</dd>
          </>
        )}
        <dt>To</dt>
        <dd>{list(to) || '—'}</dd>
        {list(cc) && (
          <>
            <dt>Cc</dt>
            <dd>{list(cc)}</dd>
          </>
        )}
        {sent_at && (
          <>
            <dt>Sent</dt>
            <dd>{absoluteTime(sent_at)}</dd>
          </>
        )}
      </dl>
      {html && text && (
        <div className="data-segmented" role="tablist" aria-label="Body format">
          {(['html', 'text'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? 'data-segment data-segment-active' : 'data-segment'}
              onClick={() => setMode(m)}
            >
              {m === 'html' ? 'HTML' : 'Text'}
            </button>
          ))}
        </div>
      )}
      {mode === 'html' && html ? (
        <iframe className="mail-frame" title="Email body" sandbox="" srcDoc={html} />
      ) : (
        <pre className="mail-text">{text || ''}</pre>
      )}
    </article>
  );
}
