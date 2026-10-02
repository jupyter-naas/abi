'use client';

/** Binary values: images shown, anything else as a hex dump on demand. */
import { useEffect, useState } from 'react';
import { Binary, FileQuestion } from 'lucide-react';
import { formatBytes, isImage } from '../data-model';
import { EmptyState } from '../data-ui';

const HEX_BYTES = 4096;
const IMAGE_LIMIT = 15 * 1024 * 1024;

export function hexDump(bytes: Uint8Array): string[] {
  const lines: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += 16) {
    const chunk = bytes.slice(offset, offset + 16);
    const hex = Array.from(chunk, (b) => b.toString(16).padStart(2, '0')).join(' ');
    const ascii = Array.from(chunk, (b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '·')).join('');
    lines.push(`${offset.toString(16).padStart(8, '0')}  ${hex.padEnd(47, ' ')}  ${ascii}`);
  }
  return lines;
}

function ImagePreview({ name, load }: { name: string; load: () => Promise<Blob | null> }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    void load().then((blob) => {
      if (cancelled) return;
      if (!blob) return setFailed(true);
      revoked = URL.createObjectURL(blob);
      setUrl(revoked);
    });
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [load]);
  if (failed) return <EmptyState icon={FileQuestion} title="Preview unavailable" />;
  if (!url) return <div className="binary-image-loading" aria-busy="true" />;
  return (
    <figure className="binary-image">
      {/* eslint-disable-next-line @next/next/no-img-element -- a blob URL, not an optimizable asset */}
      <img src={url} alt={name} />
    </figure>
  );
}

export function BinaryView({
  name,
  mediaType,
  size,
  load,
}: {
  name: string;
  mediaType?: string;
  size: number | null;
  load?: () => Promise<Blob | null>;
}) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  if (load && isImage(name, mediaType) && (size ?? 0) <= IMAGE_LIMIT) {
    return <ImagePreview name={name} load={load} />;
  }
  return (
    <div className="binary">
      <EmptyState icon={Binary} title="Binary content">
        {[formatBytes(size), mediaType].filter(Boolean).join(' · ') || 'Not text'}
      </EmptyState>
      {load && !lines && (
        <div className="binary-actions">
          <button
            type="button"
            className="data-button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              const blob = await load();
              setBusy(false);
              if (blob) setLines(hexDump(new Uint8Array(await blob.slice(0, HEX_BYTES).arrayBuffer())));
            }}
          >
            {busy ? 'Loading…' : 'Show hex dump'}
          </button>
        </div>
      )}
      {lines && (
        <>
          <pre className="binary-hex">{lines.join('\n')}</pre>
          {(size ?? 0) > HEX_BYTES && <p className="data-muted">First {formatBytes(HEX_BYTES)} shown.</p>}
        </>
      )}
    </div>
  );
}
