import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> & {
  onCheckedChange?: (checked: boolean) => void;
  label?: ReactNode;
};

// Square checkbox used for every enable/disable control in settings (replaces the old sliders).
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, onCheckedChange, label, checked, disabled, ...props },
  ref
) {
  const box = (
    <span className={cn('relative inline-flex h-4 w-4 shrink-0', !label && className)}>
      <input
        ref={ref}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        className="peer h-4 w-4 shrink-0 cursor-pointer appearance-none rounded-none border border-input bg-background transition-colors checked:border-primary checked:bg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
        {...props}
      />
      <Check
        size={12}
        strokeWidth={3}
        className="pointer-events-none absolute left-0.5 top-0.5 hidden text-primary-foreground peer-checked:block"
      />
    </span>
  );
  if (!label) return box;
  return (
    <label
      className={cn(
        'inline-flex items-center gap-2 text-sm',
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
        className
      )}
    >
      {box}
      {label}
    </label>
  );
});

/** Square radio button, matching Checkbox. Apply to a native `<input type="radio">`. */
export const radioClass =
  'h-4 w-4 shrink-0 cursor-pointer appearance-none rounded-none border border-input bg-background transition-colors checked:border-primary checked:bg-primary checked:shadow-[inset_0_0_0_3px_hsl(var(--background))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-50';
