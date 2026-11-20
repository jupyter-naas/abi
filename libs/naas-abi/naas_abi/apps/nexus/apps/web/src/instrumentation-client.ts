import { noteRouterNavigation } from '@/lib/router-navigation';

/** Next calls this when a navigation starts (link, router.push/replace, Back/Forward). */
export function onRouterTransitionStart(url: string): void {
  noteRouterNavigation(url);
}
