'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ImageIcon, Link2, Loader2, Minus, Move, Plus, RotateCcw, Upload } from 'lucide-react';
import { ModalBackdrop } from '@/components/ui/dialogs';
import { cn } from '@/lib/utils';
import {
  DEFAULT_FRAMING,
  MAX_BACKGROUND_IMAGE_BYTES,
  MAX_BACKGROUND_ZOOM,
  MIN_BACKGROUND_ZOOM,
  clampFraming,
  commitBackgroundImage,
  discardBackgroundDraft,
  fetchBackgroundDraft,
  isApiBackgroundUrl,
  panFraming,
  parseBackgroundImageUrl,
  stageBackgroundImage,
  type BackgroundFraming,
} from '@/lib/home-background';
import { authFetch } from '@/stores/auth';
import { DeskWallpaper } from './desk-wallpaper';

type Source = 'file' | 'url';

const ZOOM_STEP = 0.25;
const KEY_PAN_PX = 16;

/**
 * File → Edit background image. Opens on the current wallpaper when there is
 * one. A new image (local file or URL) is staged by the API in `.home/tmp` and
 * previewed from there. Drag to move, wheel or the controls to zoom: the
 * preview is the desk's own renderer, so the framing is what the desk shows.
 * Validate saves the new draft (moved to `.home/background-img`, old files
 * cleaned up) or the current wallpaper's new framing; Cancel discards.
 */
export function BackgroundImageDialog({
  open,
  workspaceId,
  currentBackgroundUrl,
  fallbackColor,
  onClose,
  onSaved,
}: {
  open: boolean;
  workspaceId: string;
  /** The workspace's `background_image_url`, if any. */
  currentBackgroundUrl?: string;
  fallbackColor?: string;
  onClose: () => void;
  /** The workspace's new `background_image_url`, as the API returned it. */
  onSaved: (backgroundImageUrl: string) => void;
}) {
  const [source, setSource] = useState<Source>('file');
  const [url, setUrl] = useState('');
  const [draft, setDraft] = useState<string | null>(null);
  /** The committed wallpaper being re-framed, when no new image was picked. */
  const [current, setCurrent] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageAspect, setImageAspect] = useState(0);
  const [framing, setFraming] = useState<BackgroundFraming>(DEFAULT_FRAMING);
  const [busy, setBusy] = useState<'load' | 'save' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  // Revoke the preview blob whenever it is replaced or the dialog unmounts.
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  // Natural aspect ratio: panning needs it to know how far the image overflows.
  useEffect(() => {
    if (!previewUrl) {
      setImageAspect(0);
      return;
    }
    const img = new Image();
    img.onload = () => setImageAspect(img.naturalHeight ? img.naturalWidth / img.naturalHeight : 0);
    img.src = previewUrl;
  }, [previewUrl]);

  const reset = useCallback(() => {
    setSource('file');
    setUrl('');
    setDraft(null);
    setCurrent(null);
    setPreviewUrl(null);
    setFraming(DEFAULT_FRAMING);
    setBusy(null);
    setError(null);
  }, []);

  const load = useCallback(
    async (picked: { file: File } | { url: string }) => {
      if ('file' in picked && picked.file.size > MAX_BACKGROUND_IMAGE_BYTES) {
        setError(`Image is too large (max ${MAX_BACKGROUND_IMAGE_BYTES / (1024 * 1024)} MB)`);
        return;
      }
      setBusy('load');
      setError(null);
      try {
        const name = await stageBackgroundImage(workspaceId, picked);
        const blob = await fetchBackgroundDraft(workspaceId, name);
        setDraft(name);
        setCurrent(null);
        setFraming(DEFAULT_FRAMING);
        setPreviewUrl(URL.createObjectURL(blob));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load the image');
      } finally {
        setBusy(null);
      }
    },
    [workspaceId],
  );

  // Open on the wallpaper already in place: a drive wallpaper with its framing,
  // or an external one (Settings → Theme) pre-filled in From URL and loaded.
  useEffect(() => {
    if (!open || !currentBackgroundUrl) return;
    if (!isApiBackgroundUrl(currentBackgroundUrl)) {
      setSource('url');
      setUrl(currentBackgroundUrl);
      void load({ url: currentBackgroundUrl });
      return;
    }
    const { imageUrl, framing: saved, fileName } = parseBackgroundImageUrl(currentBackgroundUrl);
    if (!imageUrl || !fileName) return;
    let cancelled = false;
    setBusy('load');
    void (async () => {
      try {
        const response = await authFetch(imageUrl);
        if (!response.ok) throw new Error('Could not load the current background image');
        const blob = await response.blob();
        if (cancelled) return;
        setCurrent(fileName);
        setFraming(saved);
        setPreviewUrl(URL.createObjectURL(blob));
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load the current background image');
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only on opening: later edits to the theme must not reset an edit in progress.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const cancel = useCallback(() => {
    if (busy === 'save') return;
    if (draft) void discardBackgroundDraft(workspaceId);
    reset();
    onClose();
  }, [busy, draft, workspaceId, reset, onClose]);

  const validate = async () => {
    const target = draft ? { draft } : current ? { current } : null;
    if (!target) return;
    setBusy('save');
    setError(null);
    try {
      const saved = await commitBackgroundImage(workspaceId, target, framing);
      onSaved(saved);
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the background image');
      setBusy(null);
    }
  };

  const pan = useCallback(
    (dx: number, dy: number) => {
      const frame = frameRef.current;
      if (!frame) return;
      const { width, height } = frame.getBoundingClientRect();
      setFraming((prev) => panFraming(prev, dx, dy, { width, height }, imageAspect));
    },
    [imageAspect],
  );

  const zoomBy = useCallback((delta: number) => {
    setFraming((prev) => clampFraming({ ...prev, zoom: Math.round((prev.zoom + delta) * 100) / 100 }));
  }, []);

  // Wheel zooms the preview. Attached by hand: React's wheel listener is
  // passive, so it cannot stop the page behind the modal from scrolling.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || !previewUrl) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      zoomBy(event.deltaY < 0 ? ZOOM_STEP / 2 : -ZOOM_STEP / 2);
    };
    frame.addEventListener('wheel', onWheel, { passive: false });
    return () => frame.removeEventListener('wheel', onWheel);
  }, [previewUrl, zoomBy]);

  const tab = (value: Source, label: string, icon: React.ReactNode) => (
    <button
      type="button"
      role="tab"
      aria-selected={source === value}
      onClick={() => {
        setSource(value);
        setError(null);
      }}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors',
        source === value ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {icon}
      {label}
    </button>
  );

  const iconButton =
    'flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40';
  const canFrame = Boolean(previewUrl) && busy === null;

  return (
    <ModalBackdrop open={open} onClose={cancel} widthClassName="max-w-2xl">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="background-image-dialog-title"
        className="border border-border bg-background p-6 shadow-2xl"
        data-testid="background-image-dialog"
      >
        <h3 id="background-image-dialog-title" className="text-base font-semibold text-foreground">
          Edit background image
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          PNG, JPEG, GIF, WEBP or AVIF, up to {MAX_BACKGROUND_IMAGE_BYTES / (1024 * 1024)} MB.
        </p>

        <div role="tablist" aria-label="Image source" className="mt-4 flex gap-1">
          {tab('file', 'From computer', <Upload size={13} />)}
          {tab('url', 'From URL', <Link2 size={13} />)}
        </div>

        <div className="mt-3">
          {source === 'file' ? (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp,image/avif"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (file) void load({ file });
                }}
              />
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const file = event.dataTransfer.files?.[0];
                  if (file && busy === null) void load({ file });
                }}
                className="flex w-full items-center justify-center gap-2 border border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-60"
              >
                <Upload size={16} />
                Choose an image or drop it here
              </button>
            </>
          ) : (
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (url.trim()) void load({ url });
              }}
            >
              <input
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/wallpaper.jpg"
                aria-label="Image URL"
                autoFocus
                className="min-w-0 flex-1 border border-border bg-muted/50 px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent"
              />
              <button
                type="submit"
                disabled={busy !== null || !url.trim()}
                className="px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted disabled:opacity-50"
              >
                Load
              </button>
            </form>
          )}
        </div>

        {/* Preview: the desk renderer itself. Drag moves, wheel zooms. */}
        <div
          ref={frameRef}
          role="img"
          aria-label={previewUrl ? 'Background image preview. Drag or use arrow keys to move, + and − to zoom.' : 'Background image preview'}
          tabIndex={previewUrl ? 0 : -1}
          className={cn(
            'relative mt-4 aspect-video w-full touch-none select-none overflow-hidden border border-border bg-muted/40 outline-none',
            previewUrl && 'cursor-grab active:cursor-grabbing',
          )}
          onPointerDown={(event) => {
            if (!canFrame) return;
            event.currentTarget.setPointerCapture(event.pointerId);
            dragRef.current = { x: event.clientX, y: event.clientY };
          }}
          onPointerMove={(event) => {
            const last = dragRef.current;
            if (!last) return;
            pan(event.clientX - last.x, event.clientY - last.y);
            dragRef.current = { x: event.clientX, y: event.clientY };
          }}
          onPointerUp={() => {
            dragRef.current = null;
          }}
          onPointerCancel={() => {
            dragRef.current = null;
          }}
          onKeyDown={(event) => {
            if (!canFrame) return;
            const moves: Record<string, [number, number]> = {
              ArrowLeft: [KEY_PAN_PX, 0],
              ArrowRight: [-KEY_PAN_PX, 0],
              ArrowUp: [0, KEY_PAN_PX],
              ArrowDown: [0, -KEY_PAN_PX],
            };
            if (moves[event.key]) {
              event.preventDefault();
              pan(...moves[event.key]);
            } else if (event.key === '+' || event.key === '=') {
              event.preventDefault();
              zoomBy(ZOOM_STEP);
            } else if (event.key === '-') {
              event.preventDefault();
              zoomBy(-ZOOM_STEP);
            }
          }}
        >
          {previewUrl ? (
            <DeskWallpaper imageUrl={previewUrl} framing={framing} fallbackColor={fallbackColor} className="absolute inset-0" />
          ) : null}
          {busy === 'load' ? (
            <div className="absolute inset-0 flex items-center justify-center bg-background/40">
              <Loader2 size={20} className="animate-spin text-muted-foreground" aria-label="Loading preview" />
            </div>
          ) : !previewUrl ? (
            <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
              <ImageIcon size={20} />
              Preview
            </span>
          ) : null}
        </div>

        <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
          <Move size={12} className="mr-1" aria-hidden />
          <span className="mr-auto">Drag to move · scroll to zoom</span>
          <button type="button" className={iconButton} disabled={!canFrame || framing.zoom <= MIN_BACKGROUND_ZOOM} onClick={() => zoomBy(-ZOOM_STEP)} title="Zoom out" aria-label="Zoom out">
            <Minus size={14} />
          </button>
          <input
            type="range"
            min={MIN_BACKGROUND_ZOOM}
            max={MAX_BACKGROUND_ZOOM}
            step={0.05}
            value={framing.zoom}
            disabled={!canFrame}
            onChange={(event) => setFraming((prev) => clampFraming({ ...prev, zoom: Number(event.target.value) }))}
            aria-label="Zoom"
            className="w-28 accent-[color:var(--workspace-accent,#22c55e)]"
          />
          <button type="button" className={iconButton} disabled={!canFrame || framing.zoom >= MAX_BACKGROUND_ZOOM} onClick={() => zoomBy(ZOOM_STEP)} title="Zoom in" aria-label="Zoom in">
            <Plus size={14} />
          </button>
          <span className="w-10 text-right tabular-nums">{Math.round(framing.zoom * 100)}%</span>
          <button type="button" className={iconButton} disabled={!canFrame} onClick={() => setFraming(DEFAULT_FRAMING)} title="Reset position and zoom" aria-label="Reset position and zoom">
            <RotateCcw size={13} />
          </button>
        </div>

        {error && (
          <p role="alert" className="mt-2 text-xs text-red-500">
            {error}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={cancel}
            disabled={busy === 'save'}
            className="px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void validate()}
            disabled={!(draft || current) || busy !== null}
            className="flex items-center gap-1.5 bg-workspace-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-workspace-accent/90 disabled:opacity-50"
          >
            {busy === 'save' && <Loader2 size={14} className="animate-spin" />}
            Validate
          </button>
        </div>
      </div>
    </ModalBackdrop>
  );
}
