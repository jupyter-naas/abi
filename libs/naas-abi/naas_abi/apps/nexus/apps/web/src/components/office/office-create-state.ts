'use client';

import { flushSync } from 'react-dom';
import { create } from 'zustand';
import {
  officeCreateHref,
  type OfficeCreateKind,
  type OfficeCreatePhase,
} from './office-create';

type OfficeCreateState = {
  kind: OfficeCreateKind | null;
  phase: OfficeCreatePhase;
  error: string | null;
};

const idle: OfficeCreateState = {
  kind: null,
  phase: 'creating',
  error: null,
};

export const useOfficeCreateStore = create<OfficeCreateState>(() => ({ ...idle }));

function writeBegin(kind: OfficeCreateKind): boolean {
  if (useOfficeCreateStore.getState().kind) return false;
  useOfficeCreateStore.setState({ kind, phase: 'creating', error: null });
  return true;
}

/** First paint of File → New: set the flag in this click, before router.push. */
export function beginOfficeCreate(kind: OfficeCreateKind): boolean {
  if (useOfficeCreateStore.getState().kind) return false;
  if (typeof document !== 'undefined') {
    let started = false;
    flushSync(() => {
      started = writeBegin(kind);
    });
    return started;
  }
  return writeBegin(kind);
}

export function pushOfficeCreate(
  router: { push: (href: string) => void },
  kind: OfficeCreateKind,
  workspaceId: string,
  templateId?: string,
): boolean {
  if (!workspaceId) return false;
  if (!beginOfficeCreate(kind)) return false;
  router.push(officeCreateHref(kind, workspaceId, templateId));
  return true;
}

export function prefetchOfficeCreate(
  router: { prefetch: (href: string) => void },
  kind: OfficeCreateKind,
  workspaceId: string,
): void {
  if (!workspaceId) return;
  router.prefetch(officeCreateHref(kind, workspaceId));
}

export function setOfficeCreatePhase(phase: OfficeCreatePhase): void {
  if (!useOfficeCreateStore.getState().kind) return;
  useOfficeCreateStore.setState({ phase, error: null });
}

export function failOfficeCreate(error: string): void {
  if (!useOfficeCreateStore.getState().kind) return;
  useOfficeCreateStore.setState({ error, phase: 'creating' });
}

export function clearOfficeCreate(): void {
  useOfficeCreateStore.setState({ ...idle });
}

export function officeCreateKindFromHref(href: string): OfficeCreateKind | null {
  if (href.includes('/documents/new')) return 'document';
  if (href.includes('/slides/new')) return 'deck';
  return null;
}

/** File > New landing: `/documents/new` or `/slides/new`. */
export function isOfficeCreateNewPath(pathname: string | null | undefined): boolean {
  return /\/(documents|slides)\/new\/?$/.test(pathname || '');
}

/** Editor route for a just-created project. `/new` is also a slug. */
export function isOfficeCreateProjectPath(pathname: string | null | undefined): boolean {
  return /\/(documents|slides)\/[^/]+\/?$/.test(pathname || '');
}
