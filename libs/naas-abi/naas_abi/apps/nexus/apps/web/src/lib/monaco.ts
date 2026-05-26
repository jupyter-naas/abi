'use client';

import { loader } from '@monaco-editor/react';

let configured = false;
let configuring: Promise<void> | null = null;

/** Load Monaco from the local package so workers don't hit CDN CORS ("Script error."). */
export function ensureMonacoConfigured(): Promise<void> {
  if (configured) return Promise.resolve();
  if (configuring) return configuring;

  configuring = import('monaco-editor')
    .then(async (monaco) => {
      loader.config({ monaco });
      await loader.init();
      configured = true;
    })
    .catch((error) => {
      configuring = null;
      console.error('Failed to configure Monaco editor:', error);
      throw error;
    });

  return configuring;
}
