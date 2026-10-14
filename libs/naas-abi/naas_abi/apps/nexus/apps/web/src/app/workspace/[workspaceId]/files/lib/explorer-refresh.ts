/**
 * File → Refresh lives in the TopNav menu, but the explorer tree's folder
 * cache lives in the sidebar. The menu fires this event; the sidebar drops
 * its cache and reloads the folders that are open.
 */
export const FILES_EXPLORER_REFRESH_EVENT = 'nexus:files-explorer-refresh';

export function requestFilesExplorerRefresh(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(FILES_EXPLORER_REFRESH_EVENT));
}
