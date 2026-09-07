/** Shared Tailwind class strings for React Aria Components. */

export const fieldInput =
  'w-full min-h-10 px-4 py-2.5 rounded-md bg-transparent border border-[var(--border)] text-[var(--text)] ' +
  'outline-none transition data-[focused]:border-[var(--secondary)] data-[invalid]:border-red-500';

export const fieldLabel = 'text-sm font-medium text-[var(--text-muted)] mb-1.5 block';

export const btnPrimary =
  'bg-primary font-semibold min-h-12 px-5 py-3.5 rounded-md transition ' +
  'data-[hovered]:opacity-90 data-[pressed]:opacity-80 data-[disabled]:opacity-60 ' +
  'outline-none data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary data-[focus-visible]:ring-offset-2';

export const btnGhost =
  'w-full flex items-center gap-3 min-h-11 px-4 py-3 rounded-md text-sm transition outline-none ' +
  'text-[var(--text-muted)] data-[hovered]:bg-[var(--accent)] data-[focus-visible]:ring-2 ' +
  'data-[focus-visible]:ring-secondary';

/* Sidebar nav links are styled by the `.sidebar-nav-*` classes in globals.css
   (shared visual language with apps/investors), not by class strings here. */

export const selectTrigger =
  'w-full flex items-center justify-between gap-2 min-h-11 px-3 py-3 rounded-md text-sm font-medium ' +
  'bg-[var(--accent)] border border-[var(--border)] text-[var(--text)] cursor-pointer outline-none ' +
  'data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary data-[pressed]:bg-[var(--surface)]';

export const selectTriggerPage =
  'select-trigger-page w-full relative flex items-center justify-center min-h-11 px-6 py-2.5 rounded-lg text-sm ' +
  'cursor-pointer outline-none transition ' +
  'data-[focus-visible]:ring-2 data-[focus-visible]:ring-white/40';

export const popover =
  'bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-lg overflow-hidden ' +
  'min-w-[var(--trigger-width)] max-h-96 overflow-y-auto outline-none';

export const popoverPage =
  'company-picker-popover bg-[var(--surface)] border border-[var(--border)] rounded-lg shadow-lg overflow-hidden max-h-96 overflow-y-auto outline-none';

export const listBoxPage = 'outline-none p-1.5 space-y-1';

export const listBoxItem =
  'list-box-item min-h-11 px-4 py-3 text-sm cursor-pointer outline-none text-[var(--text)] rounded-md ' +
  'data-[focused]:bg-[var(--accent)] data-[selected]:bg-[var(--secondary)] data-[selected]:!text-white ' +
  'data-[selected]:font-semibold data-[selected]:data-[focused]:bg-[var(--secondary)] ' +
  'data-[selected]:data-[focused]:!text-white';

export const listBoxItemPage =
  'list-box-item-page w-full block min-h-12 px-4 py-4 text-sm font-semibold uppercase tracking-wide leading-relaxed text-center ' +
  'cursor-pointer outline-none text-[var(--text-muted)] rounded-md ' +
  'transition-colors data-[hovered]:bg-[var(--accent)] data-[focused]:bg-[var(--accent)] ' +
  'data-[focus-visible]:ring-2 data-[focus-visible]:ring-inset data-[focus-visible]:ring-secondary';

export const listHeader =
  'px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]';

export const modalOverlay =
  'fixed inset-0 z-50 flex justify-start bg-black/40';

export const galleryCard =
  'glass rounded-lg p-5 card-hover block outline-none transition-colors ' +
  'data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary data-[focus-visible]:ring-offset-2 ' +
  'hover:bg-[var(--accent)] data-[hovered]:bg-[var(--accent)]';

export const modalPanel =
  'shell-chrome h-full w-[min(100%,18rem)] sm:w-64 border-r border-[var(--border)] shadow-xl outline-none flex flex-col';
