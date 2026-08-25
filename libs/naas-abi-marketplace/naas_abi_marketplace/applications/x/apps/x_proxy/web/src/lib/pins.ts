/**
 * The favorites bar: pinned authors, optionally filed into folders.
 *
 * Modelled on a browser bookmarks bar — a flat row of chips, where a chip is
 * either an author or a folder holding authors. Folders never nest: the bar is
 * one row and a menu, not a tree.
 *
 * Favorites are a working set — the handles someone comes back to across
 * sessions — so unlike the timezone they live in ``localStorage`` rather than in
 * the session. Blocked storage (private mode, embedded frames) degrades to
 * favorites that simply do not survive a reload.
 */

import { FAVORITES_LIMITS } from "@/lib/appConfig";

const PINS_KEY = "x.apps.x_proxy.pinnedUsers";

/** One pinned author. */
export type FavoriteLink = {
  kind: "link";
  /** ``u:<username>`` — an author is on the bar at most once. */
  id: string;
  username: string;
};

/** A folder of pinned authors. Folders hold links only, never other folders. */
export type FavoriteFolder = {
  kind: "folder";
  id: string;
  name: string;
  items: FavoriteLink[];
};

export type FavoriteNode = FavoriteLink | FavoriteFolder;

/**
 * Caps, from `favorites:` in `config.yaml`. Folders make room for more authors
 * than a single rail could list, but the bar is still quick access rather than
 * a second search page.
 */
export const MAX_PINNED_USERS = FAVORITES_LIMITS.maxUsers;
export const MAX_FOLDERS = FAVORITES_LIMITS.maxFolders;
export const MAX_FOLDER_NAME = FAVORITES_LIMITS.maxFolderName;

export const DEFAULT_FOLDER_NAME = "New folder";

/** Where a dragged node is being dropped. */
export type DropTarget =
  /** On the bar itself, before ``before`` — or at the end when it is ``null``. */
  | { into: "bar"; before: string | null }
  /** Inside a folder, at the end of its items. */
  | { into: "folder"; folderId: string };

function linkFor(username: string): FavoriteLink {
  return { kind: "link", id: `u:${username}`, username };
}

/** Ids only have to be unique on this bar, so the clock plus noise is enough. */
function folderId(): string {
  return `f:${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

export function makeFolder(name = DEFAULT_FOLDER_NAME): FavoriteFolder {
  return { kind: "folder", id: folderId(), name: cleanName(name), items: [] };
}

export function cleanName(name: string): string {
  return name.trim().slice(0, MAX_FOLDER_NAME) || DEFAULT_FOLDER_NAME;
}

/** Every pinned author, bar order first then folder order. */
export function listUsers(nodes: FavoriteNode[]): string[] {
  return nodes.flatMap((node) =>
    node.kind === "link"
      ? [node.username]
      : node.items.map((item) => item.username),
  );
}

export function isPinned(nodes: FavoriteNode[], username: string): boolean {
  return listUsers(nodes).includes(username);
}

export function findFolder(
  nodes: FavoriteNode[],
  id: string,
): FavoriteFolder | null {
  const found = nodes.find((node) => node.kind === "folder" && node.id === id);
  return (found as FavoriteFolder) || null;
}

export function folders(nodes: FavoriteNode[]): FavoriteFolder[] {
  return nodes.filter((node): node is FavoriteFolder => node.kind === "folder");
}

/** The folder holding ``id``, or ``null`` when it sits on the bar itself. */
export function parentOf(
  nodes: FavoriteNode[],
  id: string,
): FavoriteFolder | null {
  for (const node of nodes) {
    if (node.kind === "folder" && node.items.some((item) => item.id === id)) {
      return node;
    }
  }
  return null;
}

/**
 * Parse what storage holds.
 *
 * Reads both shapes: the plain ``["grok", …]`` written before the bar had
 * folders, and the current node list. Anything unrecognisable is dropped rather
 * than throwing — a corrupted key should cost the favorites, not the app.
 */
function parse(raw: unknown): FavoriteNode[] {
  if (!Array.isArray(raw)) return [];
  const nodes: FavoriteNode[] = [];
  const seen = new Set<string>();
  let folderCount = 0;

  const takeLink = (value: unknown): FavoriteLink | null => {
    const username =
      typeof value === "string"
        ? value
        : typeof (value as FavoriteLink)?.username === "string"
          ? (value as FavoriteLink).username
          : "";
    if (!username || seen.has(username)) return null;
    if (seen.size >= MAX_PINNED_USERS) return null;
    seen.add(username);
    return linkFor(username);
  };

  for (const entry of raw) {
    const node = entry as Partial<FavoriteFolder>;
    if (node && node.kind === "folder") {
      if (folderCount >= MAX_FOLDERS) continue;
      folderCount += 1;
      nodes.push({
        kind: "folder",
        id: typeof node.id === "string" && node.id ? node.id : folderId(),
        name: cleanName(typeof node.name === "string" ? node.name : ""),
        items: (Array.isArray(node.items) ? node.items : [])
          .map(takeLink)
          .filter((item): item is FavoriteLink => item !== null),
      });
      continue;
    }
    const link = takeLink(entry);
    if (link) nodes.push(link);
  }
  return nodes;
}

export function readFavorites(): FavoriteNode[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(PINS_KEY);
    if (!raw) return [];
    return parse(JSON.parse(raw) as unknown);
  } catch {
    return [];
  }
}

export function writeFavorites(nodes: FavoriteNode[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PINS_KEY, JSON.stringify(nodes));
  } catch {
    // Private mode / blocked storage — the favorites stay in memory only.
  }
}

/** ``nodes`` without ``id``, wherever it sits. Folders leave with their items. */
export function removeNode(nodes: FavoriteNode[], id: string): FavoriteNode[] {
  return nodes
    .filter((node) => node.id !== id)
    .map((node) =>
      node.kind === "folder"
        ? { ...node, items: node.items.filter((item) => item.id !== id) }
        : node,
    );
}

/**
 * ``nodes`` with ``username`` pinned or unpinned.
 *
 * A new favorite goes to the front of the bar, so the most recently pinned
 * author is the first chip; unpinning finds it wherever it was filed. The cap
 * refuses the new pin rather than silently dropping an older one out of a
 * folder someone organised.
 */
export function togglePinned(
  nodes: FavoriteNode[],
  username: string,
): FavoriteNode[] {
  if (isPinned(nodes, username)) {
    return removeNode(nodes, `u:${username}`);
  }
  if (listUsers(nodes).length >= MAX_PINNED_USERS) return nodes;
  return [linkFor(username), ...nodes];
}

export function addFolder(
  nodes: FavoriteNode[],
  folder: FavoriteFolder,
): FavoriteNode[] {
  if (folders(nodes).length >= MAX_FOLDERS) return nodes;
  return [...nodes, folder];
}

export function renameFolder(
  nodes: FavoriteNode[],
  id: string,
  name: string,
): FavoriteNode[] {
  return nodes.map((node) =>
    node.kind === "folder" && node.id === id
      ? { ...node, name: cleanName(name) }
      : node,
  );
}

/** The node ``id`` names, detached from wherever it was. */
function detach(
  nodes: FavoriteNode[],
  id: string,
): { rest: FavoriteNode[]; node: FavoriteNode | null } {
  const onBar = nodes.find((node) => node.id === id);
  if (onBar) {
    return { rest: nodes.filter((node) => node.id !== id), node: onBar };
  }
  let filed: FavoriteNode | null = null;
  const rest = nodes.map((node) => {
    if (node.kind !== "folder") return node;
    const item = node.items.find((entry) => entry.id === id);
    if (!item) return node;
    filed = item;
    return { ...node, items: node.items.filter((entry) => entry.id !== id) };
  });
  return { rest, node: filed };
}

/**
 * Move a favorite to ``target`` — reordering the bar, filing an author into a
 * folder, or taking one back out.
 *
 * Dropping a node on itself, or a folder into a folder, is a no-op: folders do
 * not nest, and neither does a bar item become its own neighbour.
 */
export function moveNode(
  nodes: FavoriteNode[],
  id: string,
  target: DropTarget,
): FavoriteNode[] {
  if (target.into === "bar" && target.before === id) return nodes;
  if (target.into === "folder" && target.folderId === id) return nodes;

  const { rest, node } = detach(nodes, id);
  if (!node) return nodes;

  if (target.into === "folder") {
    if (node.kind === "folder") return nodes;
    return rest.map((entry) =>
      entry.kind === "folder" && entry.id === target.folderId
        ? { ...entry, items: [...entry.items, node] }
        : entry,
    );
  }

  const at = target.before
    ? rest.findIndex((entry) => entry.id === target.before)
    : -1;
  if (at < 0) return [...rest, node];
  return [...rest.slice(0, at), node, ...rest.slice(at)];
}
