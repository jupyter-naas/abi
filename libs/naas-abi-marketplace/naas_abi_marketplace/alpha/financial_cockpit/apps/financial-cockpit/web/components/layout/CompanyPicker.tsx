'use client';

import { useRouter } from 'next/navigation';
import {
  Button,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select,
} from 'react-aria-components';

import type { CompanyConfig } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { entityPageHref } from '@/lib/routes';
import { listBoxItem, listBoxItemPage, listBoxPage, popover, popoverPage, selectTrigger, selectTriggerPage } from '@/lib/ariaStyles';

const ALL_COMPANIES_KEY = '__all__';
const ALL_COMPANIES_LABEL = 'Toutes les sociétés';

type CompanyPickerProps = {
  companies: CompanyConfig[];
  currentSlug: string | null;
  entitySlug: string;
  currentPageId: string;
  scenarioId?: string | null;
  variant?: 'sidebar' | 'page';
  className?: string;
};

export function CompanyPicker({
  companies,
  currentSlug,
  entitySlug,
  currentPageId,
  scenarioId = null,
  variant = 'sidebar',
  className = 'w-full',
}: CompanyPickerProps) {
  const router = useRouter();
  const sortedCompanies = [...companies].sort((a, b) =>
    a.display_name.localeCompare(b.display_name, 'fr', { sensitivity: 'base' }),
  );

  const selectedKey = currentSlug ?? ALL_COMPANIES_KEY;
  const triggerLabel =
    currentSlug === null
      ? ALL_COMPANIES_LABEL
      : formatEntityName(
          sortedCompanies.find((c) => c.organization_slug === currentSlug)?.display_name ??
            currentSlug,
        );

  function buildPath(companySlug: string | null): string {
    return entityPageHref(
      entitySlug,
      currentPageId,
      companySlug,
      null,
      scenarioId,
    );
  }

  const triggerClass = variant === 'page' ? selectTriggerPage : selectTrigger;
  const popoverClass = variant === 'page' ? popoverPage : popover;
  const listClass = variant === 'page' ? listBoxPage : 'outline-none p-1.5 space-y-1';
  const itemClass = variant === 'page' ? listBoxItemPage : listBoxItem;

  return (
    <Select
      aria-label="Société"
      selectedKey={selectedKey}
      onSelectionChange={(key) => {
        const value = key === ALL_COMPANIES_KEY ? null : String(key);
        router.push(buildPath(value));
      }}
      className={className}
    >
      <Label className="sr-only">Société</Label>
      <Button className={triggerClass}>
        {variant === 'page' ? (
          <>
            <span className="truncate uppercase font-semibold tracking-wide text-center w-full !text-white">
              {triggerLabel}
            </span>
            <span aria-hidden className="absolute right-4 text-white/80 shrink-0 text-base leading-none">
              ▾
            </span>
          </>
        ) : (
          <>
            <span className="truncate">{triggerLabel}</span>
            <span aria-hidden className="text-[var(--text-muted)] shrink-0">
              ▾
            </span>
          </>
        )}
      </Button>
      <Popover className={popoverClass} offset={0}>
        <ListBox selectionMode="single" className={`${listClass} w-full`}>
          <ListBoxItem
            id={ALL_COMPANIES_KEY}
            textValue={ALL_COMPANIES_LABEL}
            className={itemClass}
          >
            {ALL_COMPANIES_LABEL}
          </ListBoxItem>
          {sortedCompanies.map((company) => (
            <ListBoxItem
              key={company.organization_slug}
              id={company.organization_slug}
              textValue={formatEntityName(company.display_name)}
              className={itemClass}
            >
              {formatEntityName(company.display_name)}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
    </Select>
  );
}
