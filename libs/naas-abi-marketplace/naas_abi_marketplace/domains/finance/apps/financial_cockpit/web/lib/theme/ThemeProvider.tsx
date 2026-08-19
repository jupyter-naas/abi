'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  applyTheme,
  loadThemeModeFromStorage,
  saveThemeModeToStorage,
} from '@/lib/theme/applyTheme';
import { saveThemeConfigToApi } from '@/lib/theme/persistTheme';
import {
  createDefaultThemeColors,
  setTokenValue,
  updateExportFormat,
  updateNumberStyle,
  updateTypographyStyle,
  type ExportFormatSettings,
  type ThemeColorsState,
  type ThemeMode,
  type ThemeTokenDefinition,
} from '@/lib/theme/tokens';
import { themeConfigToColors, type ThemeConfigFile } from '@/lib/theme/themeConfigShared';
import type {
  CurrencyNumberStyleSettings,
  NumberStyleId,
  NumberStyleSettings,
  TypographyStyle,
  TypographyStyleId,
} from '@/lib/theme/typography';

type ThemeContextValue = {
  mode: ThemeMode;
  colors: ThemeColorsState;
  toggleMode: () => void;
  setMode: (mode: ThemeMode) => void;
  updateToken: (token: ThemeTokenDefinition, value: string) => void;
  updateTypographyStyle: (styleId: TypographyStyleId, patch: Partial<TypographyStyle>) => void;
  updateNumberStyle: (
    styleId: NumberStyleId,
    patch: Partial<NumberStyleSettings> | Partial<CurrencyNumberStyleSettings>,
  ) => void;
  updateExportFormat: (patch: Partial<ExportFormatSettings>) => void;
  resetColors: () => void;
  canPersistTheme: boolean;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

type ThemeProviderProps = {
  children: React.ReactNode;
  initialTheme: ThemeConfigFile;
  canPersistTheme?: boolean;
};

export function ThemeProvider({
  children,
  initialTheme,
  canPersistTheme = false,
}: ThemeProviderProps) {
  const defaultMode = initialTheme.default_mode === 'dark' ? 'dark' : 'light';
  const [mode, setModeState] = useState<ThemeMode>(defaultMode);
  const [colors, setColors] = useState<ThemeColorsState>(() => themeConfigToColors(initialTheme));
  const [ready, setReady] = useState(false);
  const persistTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const nextMode = loadThemeModeFromStorage(defaultMode);
    setModeState(nextMode);
    applyTheme(nextMode, themeConfigToColors(initialTheme));
    setReady(true);
  }, [defaultMode, initialTheme]);

  useEffect(() => {
    if (!ready) {
      return;
    }
    applyTheme(mode, colors);

    if (!canPersistTheme) {
      return;
    }

    if (persistTimerRef.current) {
      clearTimeout(persistTimerRef.current);
    }

    persistTimerRef.current = setTimeout(() => {
      void saveThemeConfigToApi(colors, defaultMode);
    }, 600);

    return () => {
      if (persistTimerRef.current) {
        clearTimeout(persistTimerRef.current);
      }
    };
  }, [canPersistTheme, colors, defaultMode, mode, ready]);

  const setMode = useCallback((nextMode: ThemeMode) => {
    setModeState(nextMode);
    saveThemeModeToStorage(nextMode);
  }, []);

  const toggleMode = useCallback(() => {
    setModeState((current) => {
      const next = current === 'light' ? 'dark' : 'light';
      saveThemeModeToStorage(next);
      return next;
    });
  }, []);

  const updateToken = useCallback((token: ThemeTokenDefinition, value: string) => {
    setColors((current) => setTokenValue(current, token, value));
  }, []);

  const updateTypographyStyleFn = useCallback(
    (styleId: TypographyStyleId, patch: Partial<TypographyStyle>) => {
      setColors((current) => updateTypographyStyle(current, styleId, patch));
    },
    [],
  );

  const updateNumberStyleFn = useCallback(
    (
      styleId: NumberStyleId,
      patch: Partial<NumberStyleSettings> | Partial<CurrencyNumberStyleSettings>,
    ) => {
      setColors((current) => updateNumberStyle(current, styleId, patch));
    },
    [],
  );

  const updateExportFormatFn = useCallback((patch: Partial<ExportFormatSettings>) => {
    setColors((current) => updateExportFormat(current, patch));
  }, []);

  const resetColors = useCallback(() => {
    setColors(createDefaultThemeColors());
  }, []);

  const value = useMemo(
    () => ({
      mode,
      colors,
      toggleMode,
      setMode,
      updateToken,
      updateTypographyStyle: updateTypographyStyleFn,
      updateNumberStyle: updateNumberStyleFn,
      updateExportFormat: updateExportFormatFn,
      resetColors,
      canPersistTheme,
    }),
    [
      canPersistTheme,
      colors,
      mode,
      resetColors,
      setMode,
      toggleMode,
      updateExportFormatFn,
      updateNumberStyleFn,
      updateToken,
      updateTypographyStyleFn,
    ],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
