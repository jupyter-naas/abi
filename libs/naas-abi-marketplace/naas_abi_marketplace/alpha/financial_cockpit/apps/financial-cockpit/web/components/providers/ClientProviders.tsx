'use client';

import { useRouter } from 'next/navigation';
import { RouterProvider } from 'react-aria-components';

import { ThemeProvider } from '@/lib/theme/ThemeProvider';
import type { ThemeConfigFile } from '@/lib/theme/themeConfigShared';

declare module 'react-aria-components' {
  interface RouterConfig {
    routerOptions: NonNullable<Parameters<ReturnType<typeof useRouter>['push']>[1]>;
  }
}

type ClientProvidersProps = {
  children: React.ReactNode;
  initialTheme: ThemeConfigFile;
  canPersistTheme?: boolean;
};

export function ClientProviders({
  children,
  initialTheme,
  canPersistTheme = false,
}: ClientProvidersProps) {
  const router = useRouter();

  return (
    <ThemeProvider initialTheme={initialTheme} canPersistTheme={canPersistTheme}>
      <RouterProvider navigate={(href) => router.push(href)}>{children}</RouterProvider>
    </ThemeProvider>
  );
}
