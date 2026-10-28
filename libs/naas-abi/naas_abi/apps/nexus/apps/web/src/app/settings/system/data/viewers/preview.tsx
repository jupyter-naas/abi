'use client';

/** The richest rendering available for an entry: structured view, then JSON, code or text. */
import { Eye, Lock } from 'lucide-react';
import { detectLanguage, formatBytes, parseJson } from '../data-model';
import type { ResourceDetail } from '../data-types';
import { EmptyState, Notice } from '../data-ui';
import { BinaryView } from './binary-view';
import { CheckpointView } from './checkpoint-view';
import { CodeView } from './code-view';
import { DataGrid } from './data-grid';
import { EmailView } from './email-view';
import { JsonTree } from './json-tree';
import { MessageView } from './message-view';
import { StatusView } from './status-view';
import { TriplesView } from './triples-view';
import { VectorView } from './vector-view';

export interface PreviewContext {
  /** The whole value (downloads); ``null`` when it cannot be fetched. */
  download?: () => Promise<Blob | null>;
  reveal?: () => void;
  revealing?: boolean;
  /** Open another entry of the same service (e.g. a checkpoint's previous step). */
  open?: (id: string) => void;
}

/** The structured ``view`` rendered by type, or ``null`` when there is none. */
export function StructuredView({ detail, ctx = {} }: { detail: ResourceDetail; ctx?: PreviewContext }) {
  const view = detail.view;
  if (!view) return null;
  switch (view.type) {
    case 'json':
      return <JsonTree value={(view as { value: unknown }).value} />;
    case 'table': {
      const v = view as { columns: { name: string; type?: string }[]; rows: unknown[][]; total?: number | null };
      return <DataGrid columns={v.columns} rows={v.rows} total={v.total} />;
    }
    case 'triples': {
      const v = view as {
        triples: [string, string, string][];
        prefixes?: Record<string, string>;
        total?: number | null;
      };
      return <TriplesView triples={v.triples} prefixes={v.prefixes} total={v.total} />;
    }
    case 'vector': {
      const v = view as {
        dimension: number;
        components: number[];
        norm?: number | null;
        metadata?: unknown;
        payload?: unknown;
      };
      return <VectorView {...v} />;
    }
    case 'email':
      return <EmailView {...(view as Parameters<typeof EmailView>[0])} />;
    case 'message':
      return <MessageView {...(view as Parameters<typeof MessageView>[0])} />;
    case 'status':
      return <StatusView {...(view as Parameters<typeof StatusView>[0])} />;
    case 'checkpoint':
      return <CheckpointView view={view as Parameters<typeof CheckpointView>[0]['view']} onOpen={ctx.open} />;
    default:
      return null;
  }
}

const CODE_HEIGHT_LINE = 18;

/** Text as a JSON tree, highlighted code, or plain text. */
export function TextPreview({ text, name, mediaType }: { text: string; name: string; mediaType?: string }) {
  const value = parseJson(text);
  if (value !== undefined) return <JsonTree value={value} />;
  const language = detectLanguage(name, mediaType, text);
  if (language !== 'plaintext') {
    const lines = text.split('\n').length;
    const height = `${Math.min(Math.max(lines * CODE_HEIGHT_LINE + 24, 120), 560)}px`;
    return <CodeView value={text} language={language} height={height} />;
  }
  return <pre className="data-text">{text}</pre>;
}

export function Preview({ detail, ctx = {} }: { detail: ResourceDetail; ctx?: PreviewContext }) {
  const structured = StructuredView({ detail, ctx });
  const content = detail.content;
  const mediaType = detail.entry.attributes.media_type;
  const canDownload = detail.entry.actions.includes('download');

  let body: React.ReactNode = structured;
  if (!body && content) {
    if (content.encoding === 'masked') {
      body = (
        <EmptyState
          icon={Lock}
          title="Value hidden"
          action={
            ctx.reveal && (
              <button type="button" className="data-button" onClick={ctx.reveal} disabled={ctx.revealing}>
                <Eye size={14} aria-hidden="true" /> {ctx.revealing ? 'Revealing…' : 'Reveal'}
              </button>
            )
          }
        >
          Revealing shows the value for 30 seconds and records it in the audit log.
        </EmptyState>
      );
    } else if (content.encoding === 'binary') {
      body = (
        <BinaryView
          name={detail.entry.name}
          mediaType={mediaType}
          size={content.size}
          load={canDownload ? ctx.download : undefined}
        />
      );
    } else {
      body = <TextPreview text={content.text ?? ''} name={detail.entry.name} mediaType={mediaType} />;
    }
  }
  if (!body) return <EmptyState icon={Eye} title="Nothing to preview" />;
  return (
    <div className="data-preview">
      {content?.truncated && (
        <Notice tone="info">
          Showing the first {formatBytes((content.text ?? '').length)}
          {content.size !== null ? ` of ${formatBytes(content.size)}` : ''}.{' '}
          {canDownload ? 'Download for the whole value.' : ''}
        </Notice>
      )}
      {body}
    </div>
  );
}
