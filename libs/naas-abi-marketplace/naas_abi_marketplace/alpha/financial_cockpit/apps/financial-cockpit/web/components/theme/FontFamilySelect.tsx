'use client';

import {
  Button as AriaButton,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select,
} from 'react-aria-components';

import { listBoxItem, popover, selectTrigger } from '@/lib/ariaStyles';
import type { ThemeFontOption } from '@/lib/theme/tokens';

type FontFamilySelectProps = {
  label: string;
  options: ThemeFontOption[];
  value: string;
  selectedKey: string;
  onChange: (value: string) => void;
  className?: string;
};

export function FontFamilySelect({
  label,
  options,
  value,
  selectedKey,
  onChange,
  className = 'w-full sm:w-64 shrink-0',
}: FontFamilySelectProps) {
  const selectedOption =
    options.find((option) => option.id === selectedKey) ??
    options.find((option) => option.value === value) ??
    options[0];

  return (
    <Select
      aria-label={label}
      selectedKey={selectedKey}
      onSelectionChange={(key) => {
        const option = options.find((item) => item.id === String(key));
        if (option) {
          onChange(option.value);
        }
      }}
      className={className}
    >
      <Label className="sr-only">{label}</Label>
      <AriaButton className={selectTrigger}>
        <span className="truncate" style={{ fontFamily: selectedOption.value }}>
          {selectedOption.label}
        </span>
        <span aria-hidden className="text-[var(--text-muted)] shrink-0">
          ▾
        </span>
      </AriaButton>
      <Popover className={popover} offset={0}>
        <ListBox selectionMode="single" className="outline-none p-1.5 space-y-1 w-full">
          {options.map((option) => (
            <ListBoxItem
              key={option.id}
              id={option.id}
              textValue={option.label}
              className={listBoxItem}
            >
              <span style={{ fontFamily: option.value }}>{option.label}</span>
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
