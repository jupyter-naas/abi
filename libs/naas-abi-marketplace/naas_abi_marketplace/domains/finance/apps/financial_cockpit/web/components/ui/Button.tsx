import { Button as RACButton, type ButtonProps } from 'react-aria-components';

import { btnGhost, btnPrimary } from '@/lib/ariaStyles';

type AppButtonProps = ButtonProps & {
  variant?: 'primary' | 'ghost';
};

export function Button({ variant = 'primary', className = '', ...props }: AppButtonProps) {
  const base = variant === 'primary' ? btnPrimary : btnGhost;
  return <RACButton className={`${base} ${className}`.trim()} {...props} />;
}
