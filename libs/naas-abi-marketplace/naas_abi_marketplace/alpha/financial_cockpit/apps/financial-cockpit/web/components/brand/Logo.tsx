import { BRAND } from '@/lib/brand';

type LogoProps = {
  size?: number;
  className?: string;
  variant?: 'default' | 'onDark' | 'plain';
};

export function Logo({ size = 28, className = '', variant = 'default' }: LogoProps) {
  const shellClass =
    variant === 'onDark'
      ? 'bg-white shadow-sm border-transparent'
      : variant === 'plain'
        ? 'logo-plain border-0 p-0 shadow-none'
        : 'logo-mark';

  return (
    <span
      className={`inline-flex items-center justify-center rounded-md ${variant === 'plain' ? '' : 'p-2'} ${shellClass} ${className}`}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={BRAND.logoSrc}
        alt={BRAND.logoAlt}
        width={size}
        height={size}
        className="block"
        style={{ width: size, height: size }}
      />
    </span>
  );
}
