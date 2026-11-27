'use client';

/** A sent email as a reader shows it. HTML renders in a sandbox with no scripts. */
import { useState } from 'react';
import { Tabs } from '@/components/ui/tabs';
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
        <Tabs
          variant="segmented"
          label="Body format"
          className="w-fit"
          value={mode}
          onChange={setMode}
          items={[
            { id: 'html', label: 'HTML' },
            { id: 'text', label: 'Text' },
          ]}
        />
      )}
      {mode === 'html' && html ? (
        <iframe className="mail-frame" title="Email body" sandbox="" srcDoc={html} />
      ) : (
        <pre className="mail-text">{text || ''}</pre>
      )}
    </article>
  );
}
