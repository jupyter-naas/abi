import { beforeEach, describe, expect, it } from 'vitest';

import { noteRouterNavigation, routerNavigationPending } from './router-navigation';

const HERE = 'https://nexus.test/workspace/ws-1/files?drive=all&view=all';
const at = (href: string) => {
  const url = new URL(href);
  return { pathname: url.pathname, search: url.search };
};

describe('routerNavigationPending', () => {
  beforeEach(() => {
    // Settle whatever an earlier test left in flight.
    noteRouterNavigation(HERE, HERE);
    routerNavigationPending(at(HERE));
  });

  it('is false when no navigation started', () => {
    expect(routerNavigationPending(at(HERE))).toBe(false);
  });

  it('is true while a navigation to another page has not landed', () => {
    noteRouterNavigation('/workspace/ws-1/chat', HERE);
    expect(routerNavigationPending(at(HERE))).toBe(true);
    expect(routerNavigationPending(at(HERE))).toBe(true);
  });

  it('is false once the location is the navigation URL, and stays false', () => {
    const target = '/workspace/ws-1/files?drive=all&view=all&source=workspace-files&path=hr';
    noteRouterNavigation(target, HERE);
    expect(routerNavigationPending(at(HERE))).toBe(true);
    expect(routerNavigationPending(at(`https://nexus.test${target}`))).toBe(false);
    expect(routerNavigationPending(at(HERE))).toBe(false);
  });

  it('ignores the hash, which Next keeps out of the page URL it compares', () => {
    noteRouterNavigation('/workspace/ws-1/chat#latest', HERE);
    expect(routerNavigationPending(at('https://nexus.test/workspace/ws-1/chat'))).toBe(false);
  });

  it('is false for Back/Forward, whose URL is already the location', () => {
    noteRouterNavigation(HERE, HERE);
    expect(routerNavigationPending(at(HERE))).toBe(false);
  });

  it('follows the latest navigation when one replaces another', () => {
    noteRouterNavigation('/workspace/ws-1/chat', HERE);
    noteRouterNavigation('/workspace/ws-1/home', HERE);
    expect(routerNavigationPending(at('https://nexus.test/workspace/ws-1/chat'))).toBe(true);
    expect(routerNavigationPending(at('https://nexus.test/workspace/ws-1/home'))).toBe(false);
  });
});
