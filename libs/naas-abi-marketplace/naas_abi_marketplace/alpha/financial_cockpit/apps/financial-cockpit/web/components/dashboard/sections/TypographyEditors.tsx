'use client';

import { FontFamilySelect } from '@/components/theme/FontFamilySelect';
import { useTheme } from '@/lib/theme/ThemeProvider';
import {
  NUMBER_CURRENCY_OPTIONS,
  NUMBER_FRACTION_DIGITS_OPTIONS,
  NUMBER_LOCALE_OPTIONS,
  NUMBER_STYLE_IDS,
  NUMBER_STYLE_LABELS,
  TYPOGRAPHY_STYLE_LABELS,
  clampFractionDigits,
  formatThemeNumber,
  numberClassName,
  numberStyleFontCssVar,
  typographyClassName,
  typographyCssVar,
  typographyFontCssVar,
  type CurrencyNumberStyleSettings,
  type NumberStyleId,
  type NumberStyleSettings,
  type TypographyStyle,
  type TypographyStyleId,
} from '@/lib/theme/typography';
import {
  numberFontOptionIdForValue,
  THEME_NUMBER_FONT_OPTIONS,
} from '@/lib/theme/tokens';
import { fieldInput } from '@/lib/ariaStyles';

const FONT_WEIGHT_OPTIONS = ['400', '500', '600', '700'] as const;

const TEXT_TRANSFORM_OPTIONS = [
  { id: 'none', label: 'Aucune' },
  { id: 'uppercase', label: 'Majuscules' },
  { id: 'lowercase', label: 'Minuscules' },
  { id: 'capitalize', label: 'Capitaliser' },
] as const;

const TYPOGRAPHY_GROUPS: { title: string; ids: TypographyStyleId[] }[] = [
  { title: 'Title & Subtitle', ids: ['title', 'subtitle'] },
  { title: 'Titres 1 à 5', ids: ['title-1', 'title-2', 'title-3', 'title-4', 'title-5'] },
  { title: 'Texte', ids: ['text'] },
];

function TypographyField({
  label,
  value,
  onChange,
  type = 'text',
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'select';
  options?: readonly { id: string; label: string }[];
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs">
      <span className="text-[var(--text-muted)]">{label}</span>
      {type === 'select' && options ? (
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={`${fieldInput} !min-h-9 py-1.5`}
        >
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={`${fieldInput} !min-h-9 py-1.5`}
        />
      )}
    </label>
  );
}

function TypographyStyleEditor({ styleId }: { styleId: TypographyStyleId }) {
  const { colors, updateTypographyStyle } = useTheme();
  const style = colors.typography[styleId];
  const meta = TYPOGRAPHY_STYLE_LABELS[styleId];

  function patch(partial: Partial<TypographyStyle>) {
    updateTypographyStyle(styleId, partial);
  }

  return (
    <div className="border-b border-[var(--border)] py-4 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{meta.label}</p>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{meta.description}</p>
          <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">
            {typographyFontCssVar(styleId)} · {typographyCssVar(styleId, 'fontSize')}
          </p>
          <p className={`mt-3 ${typographyClassName(styleId)}`}>{meta.preview}</p>
        </div>
        <div className="grid w-full gap-3 sm:w-auto sm:min-w-[28rem] sm:grid-cols-2 lg:grid-cols-3">
          <TypographyField label="Taille" value={style.fontSize} onChange={(v) => patch({ fontSize: v })} />
          <TypographyField
            label="Epaisseur"
            value={style.fontWeight}
            onChange={(v) => patch({ fontWeight: v })}
            type="select"
            options={FONT_WEIGHT_OPTIONS.map((weight) => ({ id: weight, label: weight }))}
          />
          <TypographyField
            label="Interligne"
            value={style.lineHeight}
            onChange={(v) => patch({ lineHeight: v })}
          />
          <TypographyField
            label="Espacement"
            value={style.letterSpacing}
            onChange={(v) => patch({ letterSpacing: v })}
          />
          <TypographyField
            label="Casse"
            value={style.textTransform}
            onChange={(v) => patch({ textTransform: v as TypographyStyle['textTransform'] })}
            type="select"
            options={TEXT_TRANSFORM_OPTIONS.map((option) => ({
              id: option.id,
              label: option.label,
            }))}
          />
        </div>
      </div>
    </div>
  );
}

function NumberStyleEditor({ styleId }: { styleId: NumberStyleId }) {
  const { colors, updateNumberStyle } = useTheme();
  const style = colors.numberFormat[styleId];
  const meta = NUMBER_STYLE_LABELS[styleId];

  function patch(
    partial: Partial<NumberStyleSettings> | Partial<CurrencyNumberStyleSettings>,
  ) {
    updateNumberStyle(styleId, partial);
  }

  return (
    <div className="border-b border-[var(--border)] py-4 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{meta.label}</p>
          <p className="mt-1 text-sm text-[var(--text-muted)]">{meta.description}</p>
          <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">
            {numberStyleFontCssVar(styleId)}
          </p>
          <p className={`mt-3 m-0 ${numberClassName(styleId)}`}>
            {formatThemeNumber(
              meta.previewValue,
              colors.numberFormat,
              meta.previewOptions ?? { style: styleId },
            )}
          </p>
        </div>
        <div className="grid w-full gap-3 sm:w-auto sm:min-w-[28rem] sm:grid-cols-2 lg:grid-cols-3">
          <div className="flex min-w-0 flex-col gap-1 text-xs sm:col-span-2 lg:col-span-3">
            <span className="text-[var(--text-muted)]">Police</span>
            <FontFamilySelect
              label={`Police ${meta.label}`}
              options={THEME_NUMBER_FONT_OPTIONS}
              value={style.fontFamily}
              selectedKey={numberFontOptionIdForValue(style.fontFamily)}
              onChange={(value) => patch({ fontFamily: value })}
              className="w-full"
            />
          </div>
          <TypographyField
            label="Taille"
            value={style.fontSize}
            onChange={(v) => patch({ fontSize: v })}
          />
          <TypographyField
            label="Epaisseur"
            value={style.fontWeight}
            onChange={(v) => patch({ fontWeight: v })}
            type="select"
            options={FONT_WEIGHT_OPTIONS.map((weight) => ({ id: weight, label: weight }))}
          />
          <TypographyField
            label="Locale"
            value={style.locale}
            onChange={(v) => patch({ locale: v })}
            type="select"
            options={NUMBER_LOCALE_OPTIONS.map((option) => ({
              id: option.id,
              label: option.label,
            }))}
          />
          <TypographyField
            label="Décimales max"
            value={String(style.maximumFractionDigits)}
            onChange={(v) => patch({ maximumFractionDigits: clampFractionDigits(Number(v)) })}
            type="select"
            options={NUMBER_FRACTION_DIGITS_OPTIONS.map((digits) => ({
              id: String(digits),
              label: String(digits),
            }))}
          />
          {styleId === 'currency' ? (
            <TypographyField
              label="Devise"
              value={(style as CurrencyNumberStyleSettings).currency}
              onChange={(v) => patch({ currency: v })}
              type="select"
              options={NUMBER_CURRENCY_OPTIONS.map((option) => ({
                id: option.id,
                label: option.label,
              }))}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function NumberFormatEditors() {
  return (
    <div className="border border-[var(--border)] px-4">
      {NUMBER_STYLE_IDS.map((styleId) => (
        <NumberStyleEditor key={styleId} styleId={styleId} />
      ))}
    </div>
  );
}

export function TypographyEditors() {
  return (
    <div className="space-y-6">
      {TYPOGRAPHY_GROUPS.map((group) => (
        <div key={group.title}>
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--text-muted)]">
            {group.title}
          </h4>
          <div className="border border-[var(--border)] px-4">
            {group.ids.map((styleId) => (
              <TypographyStyleEditor key={styleId} styleId={styleId} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
