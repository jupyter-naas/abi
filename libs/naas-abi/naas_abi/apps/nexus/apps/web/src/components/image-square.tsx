'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, Link2, Loader2, Search, Upload, X } from 'lucide-react';
import { browserInstanceImageSrc } from '@/lib/instance-image';
import { isImageHref, isMaterialIconValue, materialIconName, normalizeImageHref } from '@/lib/image-square';
import { cachedIconPaths, iconLabel, ICON_PREFIX, loadIconCatalog, loadIconPaths, pickerPosition, searchIconNames, SUGGESTED_ICONS } from '@/lib/ontology-icon-library';
import './image-square.css';

const PAGE_SIZE = 48;
const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml', 'image/avif'];

type Tab = 'icon' | 'upload' | 'url';

/** Details-page square shared by Ontology and Knowledge Graph (photo or fallback glyph). */
export function ImageSquare({
  src,
  fallback,
  alt = '',
  label,
  disabled,
  disabledReason,
  currentIcon,
  onCommit,
  onUpload,
}: {
  src?: string | null;
  fallback: ReactNode;
  alt?: string;
  label?: string;
  disabled?: boolean;
  disabledReason?: string;
  currentIcon?: string | null;
  onCommit?: (value: string | null) => Promise<void>;
  onUpload?: (file: File) => Promise<string>;
}) {
  const [failed, setFailed] = useState(false);
  const imageSrc = src && isMaterialIconValue(src) ? undefined : src;
  const resolved = browserInstanceImageSrc(imageSrc);
  useEffect(() => { setFailed(false); }, [src]);
  const square = (
    <span className="image-square-face">
      {resolved && !failed ? (
        <img src={resolved} alt={alt} onError={() => setFailed(true)} />
      ) : (
        fallback
      )}
    </span>
  );
  if (!onCommit) {
    return <span className="image-square">{square}</span>;
  }
  return (
    <ImageSquarePicker
      label={label || alt || 'object'}
      disabled={disabled}
      disabledReason={disabledReason}
      currentIcon={currentIcon || (src && isMaterialIconValue(src) ? src : null)}
      currentHref={imageSrc && isImageHref(imageSrc) ? imageSrc : null}
      onCommit={onCommit}
      onUpload={onUpload}
    >
      {square}
    </ImageSquarePicker>
  );
}

function ImageSquarePicker({
  children,
  label,
  disabled,
  disabledReason,
  currentIcon,
  currentHref,
  onCommit,
  onUpload,
}: {
  children: ReactNode;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
  currentIcon?: string | null;
  currentHref?: string | null;
  onCommit: (value: string | null) => Promise<void>;
  onUpload?: (file: File) => Promise<string>;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('icon');
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [retry, setRetry] = useState(0);
  const [, renderPaths] = useState(0);
  const [urlDraft, setUrlDraft] = useState('');
  const [position, setPosition] = useState({ left: 12, top: 12, width: 360, maxHeight: 480 });
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const grid = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const results = useMemo(() => searchIconNames(catalog || SUGGESTED_ICONS, query), [catalog, query]);
  const names = useMemo(() => results.slice(0, limit), [results, limit]);
  const chosen = materialIconName(currentIcon);

  useEffect(() => { if (body.current) body.current.scrollTop = 0; }, [query, catalog, tab]);
  useLayoutEffect(() => {
    if (!open) return;
    const update = () => { if (trigger.current) setPosition(pickerPosition(trigger.current.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight })); };
    update(); window.addEventListener('resize', update); window.addEventListener('scroll', update, true);
    return () => { window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, [open]);
  useEffect(() => {
    if (!open || tab !== 'icon') return;
    let active = true;
    setAssetError(null);
    void loadIconPaths(names).then(() => { if (active) renderPaths(value => value + 1); }).catch(() => { if (active) setAssetError('Could not load these icons.'); });
    return () => { active = false; };
  }, [open, names, retry, tab]);

  async function browseLibrary() {
    setLoading(true); setError(null);
    try { const data = await loadIconCatalog(); setCatalog(data.names); }
    catch { setError('Could not load the icon library. Try again.'); }
    finally { setLoading(false); }
  }
  async function commit(value: string | null) {
    setSaving(true); setError(null);
    try {
      await onCommit(value);
      setOpen(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save the image.'); }
    finally { setSaving(false); }
  }
  async function applyUrl() {
    const href = normalizeImageHref(urlDraft);
    if (!href) { setError('Paste an http(s) image URL.'); return; }
    await commit(href);
  }
  async function applyFile(file: File | undefined) {
    if (!file || !onUpload) return;
    if (!IMAGE_TYPES.includes(file.type) && !/\.(png|jpe?g|gif|webp|svg|avif)$/i.test(file.name)) {
      setError('Upload a PNG, JPG, GIF, WEBP, SVG, or AVIF image.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Image must be 5MB or smaller.');
      return;
    }
    setSaving(true); setError(null);
    try {
      await onCommit(await onUpload(file));
      setOpen(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not upload the image.'); }
    finally { setSaving(false); }
  }
  function moveInGrid(event: KeyboardEvent<HTMLDivElement>) {
    const buttons = Array.from(grid.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') || []);
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0) return;
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, ArrowDown: index + 8, ArrowUp: index - 8, Home: 0, End: buttons.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault(); event.stopPropagation(); buttons[Math.max(0, Math.min(buttons.length - 1, next))]?.focus();
  }

  return (
    <Dialog.Root open={open} onOpenChange={value => {
      if (saving) return;
      setOpen(value);
      if (value) {
        setError(null);
        setTab(currentHref ? 'url' : 'icon');
        setUrlDraft(currentHref || '');
      }
    }}>
      <Dialog.Trigger asChild>
        <button
          ref={trigger}
          type="button"
          className="image-square image-square-button"
          disabled={disabled}
          aria-label={`Change image for ${label}`}
          title={disabled ? (disabledReason || 'Your workspace role cannot change this image') : 'Change icon or image'}
        >
          {children}
          <span className="image-square-hint">Change</span>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="image-square-picker-overlay" />
        <Dialog.Content
          className="image-square-picker"
          style={position}
          onOpenAutoFocus={event => { event.preventDefault(); if (tab === 'icon') search.current?.focus(); }}
          onEscapeKeyDown={event => { if (saving) event.preventDefault(); }}
        >
          <header>
            <div>
              <Dialog.Title>Change image</Dialog.Title>
              <Dialog.Description>Icon, upload, or URL. Shared with this workspace.</Dialog.Description>
            </div>
            <Dialog.Close className="image-square-picker-close" disabled={saving} aria-label="Close image picker"><X size={15} /></Dialog.Close>
          </header>
          <div className="image-square-picker-tabs" role="tablist" aria-label="Image source">
            {([['icon', 'Icon'], ['upload', 'Upload'], ['url', 'URL']] as const).map(([id, name]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} disabled={saving} onClick={() => { setTab(id); setError(null); }}>{name}</button>
            ))}
          </div>
          {tab === 'icon' && (
            <>
              <label className="image-square-picker-search"><Search size={15} /><input ref={search} value={query} placeholder="Search icons…" aria-label="Search icons" onChange={event => {
                setQuery(event.target.value); setLimit(PAGE_SIZE); if (!catalog && !loading && event.target.value.trim()) void browseLibrary();
              }} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); grid.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus(); } }} /></label>
              <div className="image-square-picker-results-label"><span>{catalog ? `${results.length.toLocaleString()} icons` : 'Suggested icons'}</span>{loading && <Loader2 size={13} className="animate-spin" />}</div>
            </>
          )}
          <div ref={body} className="image-square-picker-body">
            {error && <p role="alert">{error}</p>}
            {tab === 'icon' && (
              <>
                {assetError && <p role="alert">{assetError} <button type="button" onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
                <div ref={grid} className="image-square-picker-grid" aria-label="Icon choices" onKeyDown={moveInGrid}>
                  {names.map(name => {
                    const paths = cachedIconPaths(name);
                    return (
                      <button key={name} type="button" aria-label={iconLabel(name)} title={iconLabel(name)} aria-pressed={name === chosen}
                        disabled={saving || disabled || !paths} onClick={() => void commit(ICON_PREFIX + name)}>
                        {paths ? <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">{paths.map((path, index) => <path key={index} d={path} />)}</svg> : <span className="image-square-picker-placeholder" />}
                        {name === chosen && <Check size={10} className="image-square-picker-check" />}
                      </button>
                    );
                  })}
                </div>
                {!names.length && !loading && <p>No icons match “{query}”.</p>}
                {!catalog && <button type="button" className="image-square-picker-more" disabled={loading} onClick={() => void browseLibrary()}>{loading ? 'Loading library…' : 'Browse full library'}</button>}
                {catalog && results.length > limit && <button type="button" className="image-square-picker-more" onClick={() => setLimit(value => value + PAGE_SIZE)}>Load more ({Math.min(limit, results.length)} of {results.length.toLocaleString()})</button>}
              </>
            )}
            {tab === 'upload' && (
              <div className="image-square-picker-upload">
                <p>Upload a square image. PNG, JPG, GIF, WEBP, SVG, or AVIF. 5MB max.</p>
                <input ref={fileInput} type="file" accept={IMAGE_TYPES.join(',')} hidden onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; void applyFile(file); }} />
                <button type="button" className="image-square-picker-more" disabled={saving || disabled || !onUpload} onClick={() => fileInput.current?.click()}>
                  {saving ? 'Uploading…' : <><Upload size={14} /> Choose image</>}
                </button>
              </div>
            )}
            {tab === 'url' && (
              <form className="image-square-picker-url" onSubmit={event => { event.preventDefault(); void applyUrl(); }}>
                <label>
                  <Link2 size={15} />
                  <input value={urlDraft} placeholder="https://…" aria-label="Image URL" onChange={event => setUrlDraft(event.target.value)} />
                </label>
                <button type="submit" className="image-square-picker-more" disabled={saving || disabled}>Save URL</button>
              </form>
            )}
          </div>
          <footer>
            <button type="button" disabled={saving || disabled || (!currentIcon && !currentHref)} onClick={() => void commit(null)}>Reset</button>
            {saving && <span role="status">Saving…</span>}
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
