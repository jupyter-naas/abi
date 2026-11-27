'use client';

import { useCallback, useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
import { createPortal } from 'react-dom';
import { ImageIcon, Link2, Loader2, Minus, Move, Plus, RotateCcw, Trash2, Upload } from 'lucide-react';
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
  removeBackgroundImage,
  stageBackgroundImage,
  wheelZoomStep,
  type BackgroundFraming,
} from '@/lib/home-background';
import { usePageState } from '@/hooks/use-page-state';
import type { PageKey } from '@/lib/page-state';
import { authFetch } from '@/stores/auth';
import { DeskWallpaper } from './desk-wallpaper';

type Source = 'file' | 'url';

const ZOOM_STEP = 0.25;
const KEY_PAN_PX = 16;

/**
 * The desk wallpaper editor, shared by Home (Edit → Desktop wallpaper, in a
 * dialog) and Settings → Theme (inline). Opens on the current wallpaper when
 * there is one. A new image (local file or URL) is staged by the API in
 * `.home/tmp` and previewed from there. Drag to move, Ctrl + wheel or the controls
 * to zoom (50% to 400%): the preview is the desk's own renderer, so the framing is what the desk
 * shows. Save stores the new draft (moved to `.home/background-img`, old files
 * cleaned up) or the current wallpaper's new framing; Cancel discards.
 */
/** What a page holding the editor in one Save (Settings › General) calls. */
export type WallpaperControl = {
  /** Commits the new image or framing; true when saved (or nothing to save), false on failure. */
  save: () => Promise<boolean>;
  /** Drops the staged image and the framing, back to the wallpaper in place. */
  discard: () => void;
};

export function BackgroundImageEditor({
  open,
  workspaceId,
  currentBackgroundUrl,
  onClose,
  onSaved,
  onRemoved,
  saveLabel = 'Validate',
  cancelLabel = 'Cancel',
  actionsContainer,
  control,
  onDirtyChange,
  keepAs,
}: {
  /** Loads the current wallpaper each time it becomes true (always true inline). */
  open: boolean;
  workspaceId: string;
  /** The workspace's `background_image_url`, if any. */
  currentBackgroundUrl?: string;
  /** After Save or Cancel: close the dialog, or reload the inline editor. */
  onClose: () => void;
  /** The workspace's new `background_image_url`, as the API returned it. */
  onSaved: (backgroundImageUrl: string) => void;
  /** After Remove wallpaper (shown when there is one): clear it from the theme. */
  onRemoved?: () => void;
  saveLabel?: string;
  cancelLabel?: string;
  /**
   * Where to render Remove / Cancel / Save instead of under the preview, e.g.
   * the top right of a settings section header (Settings > General).
   */
  actionsContainer?: HTMLElement | null;
  /**
   * Held by the page: its own Save and Discard commit or drop the wallpaper, and the editor
   * shows no Save or Cancel of its own (Remove stays).
   */
  control?: Ref<WallpaperControl>;
  /** Whether a new image or a new framing waits to be saved. */
  onDirtyChange?: (dirty: boolean) => void;
  /**
   * Where the page keeps its unsaved edits (`usePageState`): the staged image and the framing
   * survive leaving the page and come back on return, as a form's draft does.
   */
  keepAs?: PageKey;
}) {
  const [source, setSource] = useState<Source>('file');
  const [url, setUrl] = useState('');
  const [draft, setDraft] = useState<string | null>(null);
  /** The committed wallpaper being re-framed, when no new image was picked. */
  const [current, setCurrent] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageAspect, setImageAspect] = useState(0);
  const [framing, setFraming] = useState<BackgroundFraming>(DEFAULT_FRAMING);
  /** The framing of the wallpaper in place, to tell a re-framing from none. */
  const [savedFraming, setSavedFraming] = useState<BackgroundFraming>(DEFAULT_FRAMING);
  const [busy, setBusy] = useState<'load' | 'save' | 'remove' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  // The unsaved image and framing, kept for a return to the page (``keepAs``).
  const [kept, setKept] = usePageState<{ draft: string | null; framing: BackgroundFraming } | null>(
    keepAs ?? null,
    null
  );
  const keptRef = useRef(kept);
  keptRef.current = kept;

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
    setSavedFraming(DEFAULT_FRAMING);
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
    if (!open) return;
    const restore = keptRef.current;
    let cancelled = false;
    // An image staged and not saved before the page was left: back on it, framed as it was.
    if (restore?.draft) {
      const name = restore.draft;
      setBusy('load');
      void (async () => {
        try {
          const blob = await fetchBackgroundDraft(workspaceId, name);
          if (cancelled) return;
          setDraft(name);
          setCurrent(null);
          setFraming(restore.framing);
          setPreviewUrl(URL.createObjectURL(blob));
        } catch {
          // The staged image is gone (another was staged since): start from the wallpaper.
          if (!cancelled) setKept(null);
        } finally {
          if (!cancelled) setBusy(null);
        }
      })();
      return () => {
        cancelled = true;
      };
    }
    if (!currentBackgroundUrl) return;
    if (!isApiBackgroundUrl(currentBackgroundUrl)) {
      setSource('url');
      setUrl(currentBackgroundUrl);
      void load({ url: currentBackgroundUrl });
      return;
    }
    const { imageUrl, framing: saved, fileName } = parseBackgroundImageUrl(currentBackgroundUrl);
    if (!imageUrl || !fileName) return;
    setBusy('load');
    void (async () => {
      try {
        const response = await authFetch(imageUrl);
        if (!response.ok) throw new Error('Could not load the current background image');
        const blob = await response.blob();
        if (cancelled) return;
        setCurrent(fileName);
        // A re-framing not saved before the page was left comes back.
        setFraming(restore?.framing ?? saved);
        setSavedFraming(saved);
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

  // Closed some other way (dialog backdrop, Escape): drop a staged image, start clean.
  const draftRef = useRef<string | null>(null);
  draftRef.current = draft;
  useEffect(() => {
    if (open) return;
    if (draftRef.current) void discardBackgroundDraft(workspaceId);
    reset();
  }, [open, workspaceId, reset]);

  const cancel = useCallback(() => {
    if (busy === 'save') return;
    if (draft) void discardBackgroundDraft(workspaceId);
    reset();
    onClose();
  }, [busy, draft, workspaceId, reset, onClose]);

  const reframed =
    framing.x !== savedFraming.x || framing.y !== savedFraming.y || framing.zoom !== savedFraming.zoom;
  const dirty = Boolean(draft) || (Boolean(current) && reframed);
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  // Keep the unsaved edit for a return (nothing while loading: the restore is in flight).
  useEffect(() => {
    if (!keepAs || busy === 'load') return;
    setKept(dirty ? { draft, framing } : null);
  }, [keepAs, busy, dirty, draft, framing, setKept]);

  const validate = async (): Promise<boolean> => {
    const target = draft ? { draft } : current ? { current } : null;
    if (!target) return true;
    setBusy('save');
    setError(null);
    try {
      const saved = await commitBackgroundImage(workspaceId, target, framing);
      onSaved(saved);
      reset();
      onClose();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the background image');
      setBusy(null);
      return false;
    }
  };

  useImperativeHandle(control, () => ({
    save: () => (dirty ? validate() : Promise.resolve(true)),
    discard: () => {
      if (dirty) cancel();
    },
  }));

  const remove = async () => {
    setBusy('remove');
    setError(null);
    try {
      if (draft) await discardBackgroundDraft(workspaceId);
      await removeBackgroundImage(workspaceId);
      onRemoved?.();
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove the background image');
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

  // Ctrl + wheel zooms the preview (and keeps the browser from zooming the page); a plain
  // wheel scrolls the page. Attached by hand: React's wheel listener is passive, so it
  // cannot stop the event.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || !previewUrl) return;
    const onWheel = (event: WheelEvent) => {
      const step = wheelZoomStep(event, ZOOM_STEP / 2);
      if (step === null) return;
      event.preventDefault();
      zoomBy(step);
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
    <div data-testid="background-image-editor">
        <div role="tablist" aria-label="Image source" className="flex gap-1">
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

        {/* Preview: the desk renderer itself. Drag moves, Ctrl + wheel zooms. */}
        <div
          ref={frameRef}
          role="img"
          aria-label={previewUrl ? 'Background image preview. Drag or use arrow keys to move, Ctrl + scroll or + and − to zoom.' : 'Background image preview'}
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
            <DeskWallpaper imageUrl={previewUrl} framing={framing} className="absolute inset-0" />
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
          <span className="mr-auto">Drag to move · Ctrl + scroll to zoom</span>
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

      {(() => {
        const inHeader = Boolean(actionsContainer);
        const actions = (
        <div className={inHeader ? 'flex items-center gap-2' : 'mt-4 flex justify-end gap-2'}>
          {onRemoved && currentBackgroundUrl ? (
            <button
              type="button"
              onClick={() => void remove()}
              disabled={busy !== null}
              className={cn(
                'flex items-center gap-1.5 text-sm text-red-500 transition-colors hover:bg-red-500/10 disabled:opacity-50',
                inHeader ? 'h-8 px-3' : 'mr-auto px-3 py-2'
              )}
            >
              {busy === 'remove' ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              Remove wallpaper
            </button>
          ) : null}
          {control ? null : (
          <>
          <button
            type="button"
            onClick={cancel}
            disabled={busy === 'save'}
            className={cn(
              'text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50',
              inHeader ? 'h-8 px-3' : 'px-4 py-2'
            )}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => void validate()}
            disabled={!(draft || current) || busy !== null}
            className={cn(
              'flex items-center gap-1.5 bg-workspace-accent text-sm font-medium text-white transition-colors hover:bg-workspace-accent/90 disabled:opacity-50',
              inHeader ? 'h-8 px-3' : 'px-4 py-2'
            )}
          >
            {busy === 'save' && <Loader2 size={14} className="animate-spin" />}
            {saveLabel}
          </button>
          </>
          )}
        </div>
        );
        return actionsContainer ? createPortal(actions, actionsContainer) : actions;
      })()}
    </div>
  );
}
