'use client';

import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Laptop, Loader2, RefreshCw, Smartphone, Tablet } from 'lucide-react';
import { APP_PREVIEW_MESSAGE_SOURCE, previewErrorFromMessage } from '@/lib/app-projects';
import { cn } from '@/lib/utils';

type Device = 'desktop' | 'tablet' | 'phone';
const DEVICE_WIDTH: Record<Device, string> = { desktop: '100%', tablet: '820px', phone: '390px' };

type Props = {
  /** Absolute /app-preview/<token>/ URL, or null while it is minted. */
  src: string | null;
  /** Bump to reload (after an edit). */
  version: number;
  title: string;
  onError: (message: string) => void;
  /** The page (re)started: the editor clears its error list. */
  onLoadStart: () => void;
};

/**
 * Live preview of an app project (middle of the Apps editor).
 *
 * No allow-same-origin: the API also sends CSP `sandbox`, so the app runs in
 * an opaque origin and never reaches the Nexus session. The bridge the API
 * injects reports runtime errors here with postMessage.
 */
export function AppPreviewFrame({ src, version, title, onError, onLoadStart }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [device, setDevice] = useState<Device>('desktop');
  const [loading, setLoading] = useState(true);
  const [localVersion, setLocalVersion] = useState(0);
  const onErrorRef = useRef(onError);
  const onLoadStartRef = useRef(onLoadStart);
  onErrorRef.current = onError;
  onLoadStartRef.current = onLoadStart;

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return;
      const data = event.data as { source?: string; type?: string } | null;
      if (data?.source !== APP_PREVIEW_MESSAGE_SOURCE) return;
      if (data.type === 'load') {
        onLoadStartRef.current();
        return;
      }
      const message = previewErrorFromMessage(event.data);
      if (message) onErrorRef.current(message);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  useEffect(() => {
    setLoading(true);
  }, [src, version, localVersion]);

  const deviceBtn = (value: Device, Icon: typeof Laptop, label: string) => (
    <button
      type="button"
      title={label}
      onClick={() => setDevice(value)}
      className={cn(
        'rounded p-1 transition-colors hover:bg-muted hover:text-foreground',
        device === value ? 'bg-muted text-foreground' : 'text-muted-foreground',
      )}
    >
      <Icon size={14} />
    </button>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-1 border-b border-border px-2 py-1">
        <span className="mr-auto text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Preview
        </span>
        {loading && src && <Loader2 size={12} className="mr-1 animate-spin text-muted-foreground" />}
        {deviceBtn('desktop', Laptop, 'Desktop width')}
        {deviceBtn('tablet', Tablet, 'Tablet width')}
        {deviceBtn('phone', Smartphone, 'Phone width')}
        <button
          type="button"
          title="Reload preview"
          onClick={() => setLocalVersion((v) => v + 1)}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <RefreshCw size={14} />
        </button>
        {src && (
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            title="Open preview in a new tab"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <ExternalLink size={14} />
          </a>
        )}
      </div>
      <div className="relative min-h-0 flex-1 overflow-auto bg-muted/30">
        {!src ? (
          <div className="flex h-full items-center justify-center gap-2 text-xs text-muted-foreground">
            <Loader2 size={14} className="animate-spin" /> Preparing preview…
          </div>
        ) : (
          <div
            className="mx-auto h-full bg-white shadow-sm transition-[width]"
            style={{ width: DEVICE_WIDTH[device], maxWidth: '100%' }}
          >
            <iframe
              key={`${version}:${localVersion}:${src}`}
              ref={iframeRef}
              src={src}
              title={`${title} preview`}
              onLoad={() => setLoading(false)}
              className="h-full w-full border-0"
              sandbox="allow-scripts allow-forms allow-popups allow-modals allow-downloads"
            />
          </div>
        )}
      </div>
    </div>
  );
}
