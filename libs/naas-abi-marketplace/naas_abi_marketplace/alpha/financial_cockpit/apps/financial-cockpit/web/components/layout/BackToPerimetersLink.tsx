import Link from 'next/link';

const linkClassName =
  'relative z-10 inline-flex items-center gap-1 text-xs text-[var(--text-muted)] ' +
  'outline-none focus-visible:ring-2 focus-visible:ring-secondary shrink-0';

export function BackToPerimetersLink() {
  return (
    <Link href="/" className={linkClassName}>
      <span aria-hidden>←</span> Tous les périmètres
    </Link>
  );
}
