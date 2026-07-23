'use client';

import { Link } from 'react-aria-components';

import { btnGhost } from '@/lib/ariaStyles';

type ThemePageLinkProps = {
  href: string;
  isActive: boolean;
};

function PaletteIcon() {
  return (
    <svg
      className="w-5 h-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 3c-4.97 0-9 2.69-9 6 0 1.66.74 3.18 2 4.36-.28.86-.46 1.76-.52 2.68-.06.98.76 1.8 1.74 1.74.92-.06 1.82-.24 2.68-.52C9.82 19.26 10.84 20 12 20c4.97 0 9-2.69 9-6s-4.03-6-9-6z"
      />
      <circle cx="8.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="7.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ThemePageLink({ href, isActive }: ThemePageLinkProps) {
  return (
    <Link
      href={href}
      aria-label="Gérer le thème et les couleurs"
      aria-current={isActive ? 'page' : undefined}
      className={`${btnGhost} !w-auto min-h-11 min-w-11 justify-center px-3 ${
        isActive ? 'bg-[var(--accent)] !text-[var(--text)]' : ''
      }`.trim()}
    >
      <PaletteIcon />
    </Link>
  );
}
