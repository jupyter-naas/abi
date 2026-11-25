'use client';

import './email.css';

import { useState } from 'react';
import { Mail, Paperclip, Send } from 'lucide-react';
import { formatBytes } from '../data-model';
import type { ResourceDetail } from '../data-types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Textarea } from '@/components/ui/input';
import { Tabs } from '@/components/ui/tabs';
import { Kbd, RelativeTime } from '../data-ui';
import { EmailView } from '../viewers/email-view';
import type { CreateProps, ServiceView } from './types';

const ADDRESS = /^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$/;

/** Addresses from a comma- or semicolon-separated field, and the ones that are not valid. */
export function parseAddresses(value: string): { valid: string[]; invalid: string[] } {
  const parts = value
    .split(/[,;\n]/)
    .map((p) => p.trim())
    .filter(Boolean);
  return { valid: parts.filter((p) => ADDRESS.test(p)), invalid: parts.filter((p) => !ADDRESS.test(p)) };
}

/** The JSON message the API sends (see the email adapter's write format). */
export function buildMessage(fields: {
  to: string;
  cc: string;
  subject: string;
  text: string;
  html: string;
  withHtml: boolean;
}): string {
  const message: Record<string, unknown> = {
    to: parseAddresses(fields.to).valid,
    subject: fields.subject.trim(),
    text: fields.text,
  };
  const cc = parseAddresses(fields.cc).valid;
  if (cc.length) message.cc = cc;
  if (fields.withHtml && fields.html.trim()) message.html = fields.html;
  return JSON.stringify(message);
}

function slug(subject: string): string {
  return (
    subject
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48) || 'message'
  );
}

export function Composer({ busy, submit, close }: CreateProps) {
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [subject, setSubject] = useState('');
  const [text, setText] = useState('');
  const [withHtml, setWithHtml] = useState(false);
  const [html, setHtml] = useState('');
  const [previewHtml, setPreviewHtml] = useState(false);
  const [tried, setTried] = useState(false);

  const recipients = parseAddresses(to);
  const copies = parseAddresses(cc);
  const errors = {
    to: !recipients.valid.length
      ? 'Add at least one recipient.'
      : recipients.invalid.length
        ? `Not an address: ${recipients.invalid.join(', ')}`
        : null,
    cc: copies.invalid.length ? `Not an address: ${copies.invalid.join(', ')}` : null,
    subject: subject.trim() ? null : 'Add a subject.',
    body: text.trim() || (withHtml && html.trim()) ? null : 'Write a message.',
  };
  const ready = !errors.to && !errors.cc && !errors.subject && !errors.body && !busy;

  const send = async () => {
    setTried(true);
    if (!ready) return;
    await submit(slug(subject), buildMessage({ to, cc, subject, text, html, withHtml }));
  };

  const show = (error: string | null) => (tried && error ? <p className="data-field-error">{error}</p> : null);
  const invalid = (error: string | null) => (tried && error ? { 'aria-invalid': true, className: 'border-destructive' } : {});

  return (
    <form
      className="data-mail-composer"
      onSubmit={(e) => {
        e.preventDefault();
        void send();
      }}
      onKeyDown={(e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
          e.preventDefault();
          void send();
        }
      }}
    >
      <label className="data-mail-field">
        <span className="data-mail-label">To</span>
        <Input
          {...invalid(errors.to)}
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="ops@example.com, cto@example.com"
          aria-label="To"
          autoComplete="off"
          data-autofocus
        />
      </label>
      {show(errors.to)}
      <label className="data-mail-field">
        <span className="data-mail-label">Cc</span>
        <Input
          {...invalid(errors.cc)}
          value={cc}
          onChange={(e) => setCc(e.target.value)}
          placeholder="Optional"
          aria-label="Cc"
          autoComplete="off"
        />
      </label>
      {show(errors.cc)}
      <label className="data-mail-field">
        <span className="data-mail-label">Subject</span>
        <Input
          {...invalid(errors.subject)}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          aria-label="Subject"
          autoComplete="off"
        />
      </label>
      {show(errors.subject)}
      <Textarea
        className="data-mail-body"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Write your message…"
        aria-label="Message"
        rows={9}
      />
      <Checkbox className="w-fit" checked={withHtml} onCheckedChange={setWithHtml} label="Also send an HTML version" />
      {withHtml && (
        <div className="data-mail-html">
          <Tabs
            variant="segmented"
            label="HTML version"
            className="w-fit"
            value={previewHtml ? 'preview' : 'html'}
            onChange={(id) => setPreviewHtml(id === 'preview')}
            items={[
              { id: 'html', label: 'HTML' },
              { id: 'preview', label: 'Preview' },
            ]}
          />
          {previewHtml ? (
            <iframe className="data-mail-html-preview" title="HTML preview" sandbox="" srcDoc={html} />
          ) : (
            <Textarea
              className="data-mail-body data-mail-html-source"
              value={html}
              onChange={(e) => setHtml(e.target.value)}
              placeholder="<p>Hello</p>"
              aria-label="HTML version"
              rows={7}
              spellCheck={false}
            />
          )}
        </div>
      )}
      {show(errors.body)}
      <footer className="data-mail-footer">
        <span className="data-modal-hint">
          Sent from the platform sender · recorded in the audit log · <Kbd>⌘</Kbd>
          <Kbd>↵</Kbd>
        </span>
        <Button variant="secondary" onClick={close}>
          Cancel
        </Button>
        <Button type="submit" disabled={busy}>
          <Send size={14} aria-hidden="true" /> {busy ? 'Sending…' : 'Send'}
        </Button>
      </footer>
    </form>
  );
}

function EmailPreview({ detail }: { detail: ResourceDetail }) {
  if (!detail.view || detail.view.type !== 'email') return null;
  const { attachments, ...mail } = detail.view as Parameters<typeof EmailView>[0] & {
    attachments?: { name: string; type: string }[];
  };
  return (
    <div className="data-mail-preview">
      <EmailView {...mail} />
      {attachments && attachments.length > 0 && (
        <section className="data-section">
          <h4 className="data-section-title">Attachments · {attachments.length}</h4>
          <span className="data-mail-attachments">
            {attachments.map((a, i) => (
              <Badge key={`${a.name}-${i}`} title={a.type}>
                <Paperclip size={11} aria-hidden="true" /> {a.name}
              </Badge>
            ))}
          </span>
        </section>
      )}
    </div>
  );
}

export const emailView: ServiceView = {
  name: 'email',
  label: 'Email',
  description: 'Send mail as the platform, and read the sent mail the email adapter keeps.',
  icon: Mail,
  noun: { one: 'email', many: 'emails' },
  entryIcon: () => Mail,
  level: () => ({
    noun: { one: 'email', many: 'emails' },
    columns: [
      {
        id: 'to',
        label: 'To',
        width: 'minmax(140px, 0.6fr)',
        render: (e) => (
          <span className="data-mail-to" title={e.attributes.to}>
            {e.attributes.to}
          </span>
        ),
      },
      {
        id: 'size',
        label: 'Size',
        width: '72px',
        align: 'end',
        render: (e) => <span className="data-num">{formatBytes(e.size)}</span>,
      },
      { id: 'sent', label: 'Sent', width: '110px', render: (e) => <RelativeTime iso={e.modified} /> },
    ],
    emptyTitle: 'No sent mail to show',
    emptyText:
      'Compose sends through the configured email adapter. Sent messages are listed here only when the adapter keeps a copy: the filesystem adapter does, SMTP, SES and SendGrid do not.',
  }),
  summary: (entry) => (entry.attributes.from ? `From ${entry.attributes.from}` : entry.attributes.summary),
  facts: (detail) => [
    { label: 'To', value: detail.entry.attributes.to ?? '—' },
    { label: 'Sent', value: <RelativeTime iso={detail.entry.modified} /> },
    { label: 'Size', value: formatBytes(detail.entry.size) },
  ],
  preview: (detail) => (detail.view?.type === 'email' ? <EmailPreview detail={detail} /> : null),
  createLabel: 'Compose',
  create: (props) => <Composer {...props} />,
  deleteWarning: () =>
    'This deletes the kept copy only. The message was already delivered and is not recalled.',
};
