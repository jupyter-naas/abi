/** Mount helpers for the System app component tests (jsdom). */
import { act, createElement, type ComponentType } from 'react';
import { createRoot, type Root } from 'react-dom/client';

export interface Mounted {
  host: HTMLDivElement;
  click: (element: Element | null) => Promise<void>;
  /** Set an input's value the way a user would (React sees the change). */
  type: (element: Element | null, value: string) => Promise<void>;
  /** Let pending promises and the renders they cause settle. */
  flush: () => Promise<void>;
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
    type: async (element, value) => {
      if (!element) throw new Error('nothing to type into');
      const input = element as HTMLInputElement | HTMLTextAreaElement;
      const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setValue = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      await act(async () => {
        setValue?.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
    },
    flush: async () => {
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    },
    unmount: async () => {
      await act(async () => root.unmount());
      host.remove();
    },
  };
}
