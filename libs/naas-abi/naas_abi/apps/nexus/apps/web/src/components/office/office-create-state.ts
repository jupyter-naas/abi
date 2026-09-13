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

/** First paint of File → New: set the flag in this click, before create runs. */
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

function navigateOfficeCreate(
  router: { replace: (href: string) => void; push: (href: string) => void },
  href: string,
): void {
  setOfficeCreatePhase('opening');
  if (typeof router.replace === 'function') {
    router.replace(href);
    return;
  }
  router.push(href);
}

/** File → New: paint overlay and POST now. Do not wait for /new to compile. */
export function pushOfficeCreate(
  router: { replace: (href: string) => void; push: (href: string) => void },
  kind: OfficeCreateKind,
  workspaceId: string,
  templateId?: string,
): boolean {
  if (!workspaceId) return false;
  if (!beginOfficeCreate(kind)) return false;
  void (async () => {
    try {
      if (kind === 'document') {
        const { startNewDocument } = await import('@/lib/create-documents-project');
        await startNewDocument(
          workspaceId,
          (href) => navigateOfficeCreate(router, href),
          templateId,
        );
        return;
      }
      const { startNewPresentation } = await import('@/lib/create-slides-project');
      const openDeck = (href: string) => navigateOfficeCreate(router, href);
      if (templateId) {
        await startNewPresentation(workspaceId, openDeck, templateId);
      } else {
        await startNewPresentation(workspaceId, openDeck);
      }
    } catch (error) {
      const fallback =
        kind === 'document'
          ? 'Could not create the document.'
          : 'Could not create the deck.';
      failOfficeCreate((error as Error).message || fallback);
    }
  })();
  return true;
}

export function prefetchOfficeCreate(
  router: { prefetch: (href: string) => void },
  kind: OfficeCreateKind,
  workspaceId: string,
): void {
  if (!workspaceId) return;
  router.prefetch(officeCreateHref(kind, workspaceId));
  // Warm the editor route so File → New does not compile [slug] after POST.
  const section = kind === 'document' ? 'documents' : 'slides';
  router.prefetch(`/workspace/${workspaceId}/${section}/untitled-prefetch`);
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
