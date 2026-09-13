'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { resolveSheetsPreviewAssets } from './sheets-assets';
import {
  computeSheetsPreviewScale,
  countSlideSections,
  isSheetsPreviewMessage,
  prepareSheetsPreviewHtml,
  sheetsPreviewIndexFromScroll,
  sheetsPreviewScrollTop,
  SHEETS_PREVIEW_IMAGES_READY_TIMEOUT_MS,
  SHEETS_PREVIEW_MESSAGE_SOURCE,
  SHEETS_STAGE_HEIGHT,
  SHEETS_STAGE_WIDTH,
  type SheetsPreviewFromParentMessage,
  type SheetsTextEdit,
} from './sheets-preview-fit';

export interface SheetsPreviewFrameProps {
  html: string;
  workspaceId?: string;
  slug?: string;
  className?: string;
  title?: string;
  selectedIndex?: number;
  onSelectedIndexChange?: (index: number) => void;
  manualEdit?: boolean;
  onManualEditCommit?: (edits: SheetsTextEdit[]) => void;
}

/**
 * Workbook preview: fixed 1280x720 tabs stacked vertically, contain-scaled in the
 * center pane. Tab strip selection jumps scroll; scrolling updates the active tab.
 *
 * Sandbox omits allow-same-origin. Metrics and Manual edit use the postMessage
 * bridge. Viewport-fit is stripped in prepareSheetsPreviewHtml so the parent
 * contain-scale is the only scale.
 *
 * Relative ``assets/`` paths 404 inside srcDoc. The parent fetches the sheets
 * asset route with Bearer auth and inlines data-URLs before setting srcDoc.
 */
export function SheetsPreviewFrame({
  html,
  workspaceId = '',
  slug = '',
  className,
  title = 'Sheets preview',
  selectedIndex = 0,
  onSelectedIndexChange,
  manualEdit = false,
  onManualEditCommit,
}: SheetsPreviewFrameProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const manualEditRef = useRef(manualEdit);
  const onManualEditCommitRef = useRef(onManualEditCommit);
  const acceptEditsUntilRef = useRef(0);
  const tabCountRef = useRef(1);
  const [scale, setScale] = useState(1);
  const [docHeight, setDocHeight] = useState(SHEETS_STAGE_HEIGHT);
  const [hostHeight, setHostHeight] = useState(0);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [imagesReady, setImagesReady] = useState(false);

  manualEditRef.current = manualEdit;
  onManualEditCommitRef.current = onManualEditCommit;

  const stageHeightForCount = (count: number) =>
    Math.max(1, count) * SHEETS_STAGE_HEIGHT;

  useEffect(() => {
    let cancelled = false;
    setImagesReady(false);
    const count = Math.max(1, countSlideSections(html));
    tabCountRef.current = count;
    setDocHeight(stageHeightForCount(count));
    void resolveSheetsPreviewAssets(html, workspaceId, slug).then((resolved) => {
      if (cancelled) return;
      const nextCount = Math.max(1, countSlideSections(resolved));
      tabCountRef.current = nextCount;
      setDocHeight(stageHeightForCount(nextCount));
      setPreviewHtml(prepareSheetsPreviewHtml(resolved));
    });
    return () => {
      cancelled = true;
    };
  }, [html, workspaceId, slug]);

  useEffect(() => {
    if (imagesReady) return;
    const timer = window.setTimeout(
      () => setImagesReady(true),
      SHEETS_PREVIEW_IMAGES_READY_TIMEOUT_MS,
    );
    return () => window.clearTimeout(timer);
  }, [previewHtml, imagesReady]);

  const measureHost = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const { width, height } = host.getBoundingClientRect();
    setHostHeight(height);
    setScale(computeSheetsPreviewScale(width, height));
  }, []);

  useLayoutEffect(() => {
    measureHost();
  }, [measureHost]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => measureHost());
    ro.observe(host);
    return () => ro.disconnect();
  }, [measureHost]);

  const postManualEdit = useCallback((enabled: boolean) => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    if (!enabled) acceptEditsUntilRef.current = Date.now() + 1500;
    const msg: SheetsPreviewFromParentMessage = {
      source: SHEETS_PREVIEW_MESSAGE_SOURCE,
      type: 'set-manual-edit',
      enabled,
    };
    win.postMessage(msg, '*');
  }, []);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return;
      if (!isSheetsPreviewMessage(event.data)) return;
      if (
        event.data.type === 'metrics' ||
        event.data.type === 'ready' ||
        event.data.type === 'images-ready'
      ) {
        if (typeof event.data.height === 'number' && event.data.height > 0) {
          setDocHeight(
            Math.max(event.data.height, stageHeightForCount(tabCountRef.current)),
          );
        }
        if (event.data.type === 'images-ready') setImagesReady(true);
        if (event.data.type === 'ready' && manualEditRef.current) {
          postManualEdit(true);
        }
        return;
      }
      if (event.data.type === 'edit-commit') {
        if (!manualEditRef.current && Date.now() > acceptEditsUntilRef.current) return;
        onManualEditCommitRef.current?.(event.data.edits);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [postManualEdit]);

  useEffect(() => {
    if (!previewHtml || !imagesReady) return;
    postManualEdit(manualEdit);
  }, [manualEdit, previewHtml, imagesReady, postManualEdit]);

  const ignoreScrollRef = useRef(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const target = sheetsPreviewScrollTop(selectedIndex, scale);
    ignoreScrollRef.current = true;
    if (Math.abs(host.scrollTop - target) >= SHEETS_STAGE_HEIGHT * scale * 0.25) {
      host.scrollTo({ top: target });
    }
    const timer = window.setTimeout(() => {
      ignoreScrollRef.current = false;
    }, 250);
    return () => window.clearTimeout(timer);
  }, [selectedIndex, scale, previewHtml]);

  const scaledW = SHEETS_STAGE_WIDTH * scale;
  const scaledH = docHeight * scale;
  const fitsInHost = hostHeight > 0 && scaledH <= hostHeight + 0.5;
  const topPad = fitsInHost ? Math.max(0, (hostHeight - scaledH) / 2) : 0;

  return (
    <div
      ref={hostRef}
      className={cn('absolute inset-0 overflow-auto bg-muted', className)}
      onScroll={() => {
        if (!onSelectedIndexChange || ignoreScrollRef.current) return;
        const host = hostRef.current;
        if (!host) return;
        const next = sheetsPreviewIndexFromScroll(host.scrollTop, scale);
        if (next !== selectedIndex) onSelectedIndexChange(next);
      }}
    >
      <div
        className="relative mx-auto overflow-hidden"
        style={{
          width: scaledW,
          height: scaledH,
          marginTop: topPad,
        }}
      >
        {previewHtml ? (
          <iframe
            ref={iframeRef}
            title={title}
            sandbox="allow-scripts allow-downloads"
            srcDoc={previewHtml}
            className={cn(
              'block border-0 transition-opacity duration-150',
              imagesReady ? 'opacity-100' : 'opacity-0',
            )}
            style={{
              width: SHEETS_STAGE_WIDTH,
              height: docHeight,
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
            }}
          />
        ) : null}
        {!imagesReady && (
          <div
            className="absolute inset-0 flex items-center justify-center gap-2 bg-muted text-sm text-muted-foreground"
            aria-hidden="true"
          >
            <Loader2 size={16} className="animate-spin" />
            Loading sheets…
          </div>
        )}
      </div>
    </div>
  );
}
