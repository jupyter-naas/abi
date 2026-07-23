'use client';

import { useMemo, useState } from 'react';

import { fieldInput } from '@/lib/ariaStyles';
import { FontFamilySelect } from '@/components/theme/FontFamilySelect';
import { PageTitle } from '@/components/layout/PageTitle';
import { Button } from '@/components/ui/Button';
import { NumberFormatEditors, TypographyEditors } from '@/components/dashboard/sections/TypographyEditors';
import { ExportFormatEditor } from '@/components/dashboard/sections/ExportFormatEditor';
import { useTheme } from '@/lib/theme/ThemeProvider';
import { formatThemeNumber } from '@/lib/theme/typography';
import {
  fontOptionIdForValue,
  getTokenValue,
  THEME_FONT_OPTIONS,
  THEME_TOKEN_DEFINITIONS,
  type ThemeColorsState,
  type ThemeMode,
  type ThemeTokenDefinition,
} from '@/lib/theme/tokens';

function ColorSwatch({ value }: { value: string }) {
  return (
    <span
      className="inline-block h-9 w-9 shrink-0 border border-[var(--border)]"
      style={{ backgroundColor: value }}
      aria-hidden
    />
  );
}

function FontFamilyRow({ token }: { token: ThemeTokenDefinition }) {
  const { colors, updateToken } = useTheme();
  const value = getTokenValue(colors, token);
  const selectedKey = fontOptionIdForValue(value);

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] py-4 last:border-b-0">
      <FontFamilySelect
        label={token.label}
        options={THEME_FONT_OPTIONS}
        value={value}
        selectedKey={selectedKey}
        onChange={(nextValue) => updateToken(token, nextValue)}
      />

      <div className="min-w-0 flex-1 basis-48">
        <p className="font-semibold">{token.label}</p>
        <p className="mt-1 text-sm text-[var(--text-muted)]">{token.description}</p>
        <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">{token.cssVar}</p>
      </div>
    </div>
  );
}

function TokenRow({ token }: { token: ThemeTokenDefinition }) {
  const { colors, updateToken } = useTheme();
  const value = getTokenValue(colors, token);

  if (token.type === 'font') {
    return <FontFamilyRow token={token} />;
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] py-4 last:border-b-0">
      <div className="flex items-center gap-2 shrink-0">
        <ColorSwatch value={value} />
        <input
          type="color"
          value={value}
          onChange={(event) => updateToken(token, event.target.value)}
          aria-label={`Couleur ${token.label}`}
          className="h-9 w-12 cursor-pointer border border-[var(--border)] bg-transparent p-0"
        />
        <input
          type="text"
          value={value}
          onChange={(event) => updateToken(token, event.target.value)}
          aria-label={`Code hex ${token.label}`}
          className={`${fieldInput} w-28 sm:w-32`}
        />
      </div>

      <div className="min-w-0 flex-1 basis-48">
        <p className="font-semibold">{token.label}</p>
        <p className="mt-1 text-sm text-[var(--text-muted)]">{token.description}</p>
        <p className="mt-1 font-mono text-xs text-[var(--text-muted)]">
          {token.cssVar}
          {token.type === 'color' ? ` · ${value}` : ''}
        </p>
      </div>
    </div>
  );
}

function ThemePreview({
  colors,
  viewMode,
}: {
  colors: ThemeColorsState;
  viewMode: ThemeMode;
}) {
  const mode = colors[viewMode];

  const panelStyle = useMemo(
    () => ({
      backgroundColor: mode.bg,
      color: mode.text,
      borderColor: mode.border,
    }),
    [mode],
  );

  return (
    <div
      className="h-full border border-[var(--border)] p-5"
      style={{ ...panelStyle, fontFamily: colors.fontFamily }}
    >
      <p
        className="text-xs font-semibold uppercase tracking-wide"
        style={{ color: mode['text-muted'] }}
      >
        Aperçu — mode {viewMode === 'light' ? 'clair' : 'sombre'}
      </p>

      <div
        className="mt-4 border p-4"
        style={{ backgroundColor: mode.surface, borderColor: mode.border }}
      >
        <p className="text-lg font-bold" style={{ color: colors.brand.primary }}>
          Primary · {colors.brand.primary}
        </p>
        <p className="mt-2 font-semibold" style={{ color: colors.brand.secondary }}>
          Secondary · {colors.brand.secondary}
        </p>
        <p className="mt-4">Texte principal</p>
        <p className="mt-1 text-sm" style={{ color: mode['text-muted'] }}>
          Texte atténué
        </p>
        <div
          className="mt-4 inline-block px-4 py-2 text-sm font-semibold text-white"
          style={{ backgroundColor: colors.brand.primary }}
        >
          Bouton primary
        </div>
      </div>

      <div
        className="mt-4 border p-3 text-sm"
        style={{ backgroundColor: mode.accent, borderColor: mode.border }}
      >
        Zone de survol · {mode.accent}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="border p-2" style={{ borderColor: mode.border }}>
          <span style={{ color: mode['text-muted'] }}>--primary</span>
          <br />
          {colors.brand.primary}
        </div>
        <div className="border p-2" style={{ borderColor: mode.border }}>
          <span style={{ color: mode['text-muted'] }}>--secondary</span>
          <br />
          {colors.brand.secondary}
        </div>
        <div className="border p-2" style={{ borderColor: mode.border }}>
          <span style={{ color: mode['text-muted'] }}>--accent</span>
          <br />
          {mode.accent}
        </div>
        <div className="border p-2" style={{ borderColor: mode.border }}>
          <span style={{ color: mode['text-muted'] }}>--border</span>
          <br />
          {mode.border}
        </div>
      </div>

      <div className="mt-6 space-y-2 border-t pt-4" style={{ borderColor: mode.border }}>
        <p className="type-title">Title</p>
        <p className="type-subtitle">Subtitle descriptif</p>
        <p className="type-title-3">Titre 3</p>
        <p className="type-text">Texte de corps</p>
        <p className="type-number-decimal m-0">
          {formatThemeNumber(1234567, colors.numberFormat, { style: 'decimal' })}
        </p>
        <p className="type-number-percent m-0">
          {formatThemeNumber(0.256, colors.numberFormat, {
            style: 'percent',
            percentInput: 'rate',
          })}
        </p>
        <p className="type-number-currency m-0">
          {formatThemeNumber(1234567, colors.numberFormat, { style: 'currency' })}
        </p>
      </div>
    </div>
  );
}

function colorTokensForView(viewMode: ThemeMode): ThemeTokenDefinition[] {
  const brand = THEME_TOKEN_DEFINITIONS.filter(
    (token) => token.scope === 'brand' && token.type === 'color',
  );
  const mode = THEME_TOKEN_DEFINITIONS.filter(
    (token) => token.scope === viewMode && token.type === 'color',
  );
  return [...brand, ...mode];
}

function fontTokens(): ThemeTokenDefinition[] {
  return THEME_TOKEN_DEFINITIONS.filter((token) => token.type === 'font');
}

function ResetIcon() {
  return (
    <svg
      className="h-5 w-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v5h5" />
    </svg>
  );
}

export function ThemeSection() {
  const { colors, resetColors } = useTheme();
  const [viewMode, setViewMode] = useState<ThemeMode>('light');

  const allColorTokens = colorTokensForView(viewMode);
  const typographyTokens = fontTokens();

  const modeButtonClass =
    '!w-auto min-h-11 flex-1 justify-center px-5 py-2.5 text-sm font-semibold border border-[var(--border)]';

  return (
    <div className="fade-in flex min-h-0 flex-col gap-4 lg:min-h-0 lg:flex-1">
      <div className="shrink-0">
        <PageTitle>Thème & couleurs</PageTitle>
        <p className="type-subtitle m-0">
          Référence unique des couleurs et de la typographie du portail. Les modifications sont
          appliquées immédiatement et enregistrées dans votre navigateur.
        </p>
        <div className="flex items-stretch justify-between gap-3 pt-4">
          <div className="grid min-w-0 flex-1 grid-cols-2 gap-3 sm:max-w-md">
            <Button
              variant={viewMode === 'light' ? 'primary' : 'ghost'}
              onPress={() => setViewMode('light')}
              className={`${modeButtonClass} ${
                viewMode === 'light' ? 'border-[var(--primary)]' : ''
              }`}
            >
              Mode clair
            </Button>
            <Button
              variant={viewMode === 'dark' ? 'primary' : 'ghost'}
              onPress={() => setViewMode('dark')}
              className={`${modeButtonClass} ${
                viewMode === 'dark' ? 'border-[var(--primary)]' : ''
              }`}
            >
              Mode sombre
            </Button>
          </div>
          <Button
            variant="ghost"
            onPress={resetColors}
            aria-label="Réinitialiser les couleurs"
            className="!w-auto min-h-11 min-w-11 shrink-0 justify-center border border-[var(--border)] px-3"
          >
            <ResetIcon />
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="kpi-card space-y-8 lg:min-h-0 lg:overflow-y-auto">
          <section>
            <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
              Color
            </h3>
            <div className="border border-[var(--border)] px-4">
              {allColorTokens.map((token) => (
                <TokenRow key={token.id} token={token} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
              Format des nombres
            </h3>
            <p className="mb-4 text-sm text-[var(--text-muted)]">
              Décimales max, locale et devise pour les montants, pourcentages et nombres affichés dans
              le portail.
            </p>
            <NumberFormatEditors />
          </section>

          <section>
            <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
              Export de données
            </h3>
            <ExportFormatEditor />
          </section>

          {typographyTokens.length > 0 ? (
            <section>
              <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
                Typographie
              </h3>
              <div className="border border-[var(--border)] px-4">
                {typographyTokens.map((token) => (
                  <TokenRow key={token.id} token={token} />
                ))}
              </div>
              <div className="mt-6">
                <TypographyEditors />
              </div>
            </section>
          ) : null}
        </div>

        <aside className="kpi-card lg:min-h-0 lg:overflow-y-auto">
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
            Aperçu
          </h3>
          <ThemePreview colors={colors} viewMode={viewMode} />
        </aside>
      </div>
    </div>
  );
}
