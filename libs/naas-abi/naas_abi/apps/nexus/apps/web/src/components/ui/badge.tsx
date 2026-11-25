import type { HTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

export const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-none px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      variant: {
        neutral: 'bg-muted text-muted-foreground',
        primary: 'bg-primary/10 text-primary',
        success: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
        info: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
        destructive: 'bg-destructive/10 text-destructive',
        warning: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
        outline: 'border border-border text-muted-foreground',
      },
      /** Identifiers, prefixes, encodings: monospace. */
      mono: { true: 'font-mono', false: '' },
    },
    defaultVariants: { variant: 'neutral', mono: false },
  }
);

export function Badge({
  className,
  variant,
  mono,
  ...props
}: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant, mono }), className)} {...props} />;
}
