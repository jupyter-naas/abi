'use client';

import { Button as RACButton } from 'react-aria-components';

type BurgerMenuButtonProps = {
  onPress: () => void;
  className?: string;
  'aria-expanded'?: boolean;
};

export function BurgerMenuButton({
  onPress,
  className = '',
  'aria-expanded': ariaExpanded,
}: BurgerMenuButtonProps) {
  return (
    <RACButton
      aria-label={ariaExpanded ? 'Fermer le menu' : 'Ouvrir le menu'}
      aria-expanded={ariaExpanded}
      onPress={onPress}
      className={
        `min-h-11 min-w-11 p-3 rounded-md border border-[var(--border)] outline-none ` +
        `data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary ${className}`.trim()
      }
    >
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </RACButton>
  );
}
