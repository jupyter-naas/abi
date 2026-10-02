/** Mount helpers for the System app component tests (jsdom). */
import { act, createElement, type ComponentType } from 'react';
import { createRoot, type Root } from 'react-dom/client';

export interface Mounted {
  host: HTMLDivElement;
  click: (element: Element | null) => Promise<void>;
  unmount: () => Promise<void>;
}

export async function mount<P extends object>(component: ComponentType<P>, props: P): Promise<Mounted> {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement('div');
  document.body.append(host);
  const root: Root = createRoot(host);
  await act(async () => root.render(createElement(component, props)));
  return {
    host,
    click: async (element) => {
      if (!element) throw new Error('nothing to click');
      await act(async () => (element as HTMLElement).click());
    },
    unmount: async () => {
      await act(async () => root.unmount());
      host.remove();
    },
  };
}
