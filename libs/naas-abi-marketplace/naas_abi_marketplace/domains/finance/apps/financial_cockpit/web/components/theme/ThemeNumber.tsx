'use client';

import { useTheme } from '@/lib/theme/ThemeProvider';
import {
  formatThemeNumber,
  numberClassName,
  type FormatThemeNumberOptions,
} from '@/lib/theme/typography';

export type ThemeNumberProps = FormatThemeNumberOptions & {
  value: number;
  className?: string;
};

export function ThemeNumber({
  value,
  className,
  style = 'decimal',
  ...options
}: ThemeNumberProps) {
  const { colors } = useTheme();
  const resolvedClassName = className ?? numberClassName(style);

  return (
    <span className={resolvedClassName}>
      {formatThemeNumber(value, colors.numberFormat, { style, ...options })}
    </span>
  );
}
