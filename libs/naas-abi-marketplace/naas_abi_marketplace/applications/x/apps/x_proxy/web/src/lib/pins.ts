/**
 * The favorites bars: pinned authors, or pinned posts, filed into folders.
 *
 * Modelled on a browser bookmarks bar - a flat row of chips, where a chip is
 * either a link or a folder holding links. Folders never nest: the bar is one
 * row and a menu, not a tree.
 *
 * There are two bars, one per :type:`FavoritesScope`, and they never mix: the
 * Users section pins authors, a post's page pins posts, each in its own storage
 * key. Which bar a page shows is `favorites:` in `config.yaml`.
 *
 * Favorites are a working set - the handles someone comes back to across
 * sessions - so unlike the timezone they live in ``localStorage`` rather than in
 * the session. Blocked storage (private mode, embedded frames) degrades to
 * favorites that simply do not survive a reload.
 */

import { FAVORITES_LIMITS } from "@/lib/appConfig";

/**
 * One bar per scope, one storage key per bar. Authors and posts are never in
 * the same bar: a chip means "go to this author" or "go to this post", and
 * mixing them would make the bar unreadable.
 */
export type FavoritesScope = "users" | "posts";

const PINS_KEYS: Record<FavoritesScope, string> = {
  users: "x.apps.x_proxy.pinnedUsers",
  posts: "x.apps.x_proxy.pinnedPosts",
};

/**
 * One pinned thing: an author, or a post.
 *
 * ``id`` is what the bar is keyed by, so nothing is pinned twice: ``u:<handle>``
 * for an author, ``p:<tweet id>`` for a post. A post pin also carries the
 * author it belongs to, since that is how its page is addressed.
 */
export type FavoriteLink = {
  kind: "link";
  id: string;
  username: string;
  /** Set on a post pin: the tweet the chip opens. */
  postId?: string;
  /** What the chip reads. Defaults to `@username` for an author. */
  label?: string;
  /** Longer text for the chip's tooltip - a post's own words. */
  hint?: string;
  /** Where the pin was made from, so reopening restores the back link. */
  from?: string;
  /** Search needle when pinned from Search Tweets. */
  q?: string;
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
  /** On the bar itself, before ``before`` - or at the end when it is ``null``. */
  | { into: "bar"; before: string | null }
  /** Inside a folder, at the end of its items. */
  | { into: "folder"; folderId: string };

export function userLink(username: string): FavoriteLink {
  return { kind: "link", id: `u:${username}`, username };
}

/** How much of a post's text the chip's tooltip carries. */
export const MAX_POST_HINT = 140;

/**
 * A pinned post.
 *
 * The chip reads the **tweet id** - that is what identifies a post, and what a
 * reader looking for one has in hand. Its own words go to the tooltip, where a
 * long line costs nothing.
 */
export function postLink(
  postId: string,
  username: string,
  text = "",
  from?: string | null,
  q?: string | null,
): FavoriteLink {
  const trimmed = text.trim().replace(/\s+/g, " ");
  const origin = from?.trim() || undefined;
  const needle = q?.trim() || undefined;
  return {
    kind: "link",
    id: `p:${postId}`,
    username,
    postId,
    label: postId,
    hint:
      trimmed.length > MAX_POST_HINT
        ? `${trimmed.slice(0, MAX_POST_HINT - 1)}…`
        : trimmed || undefined,
    from: origin,
    q: origin === "tweets" ? needle : undefined,
  };
}

/** What a chip reads: a post's id, or the author's handle. */
export function labelOf(link: FavoriteLink): string {
  return link.label || `@${link.username}`;
}

/** What a chip's tooltip reads: the post's words when it has them. */
export function hintOf(link: FavoriteLink): string {
  return link.hint || labelOf(link);
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

/** Every pinned link, bar order first then folder order. */
export function listLinks(nodes: FavoriteNode[]): FavoriteLink[] {
  return nodes.flatMap((node) => (node.kind === "link" ? [node] : node.items));
}

/** Ids of everything pinned - what a pin button checks itself against. */
export function listIds(nodes: FavoriteNode[]): string[] {
  return listLinks(nodes).map((link) => link.id);
}

export function isPinned(nodes: FavoriteNode[], id: string): boolean {
  return listIds(nodes).includes(id);
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
 * than throwing - a corrupted key should cost the favorites, not the app.
 */
function parse(raw: unknown): FavoriteNode[] {
  if (!Array.isArray(raw)) return [];
  const nodes: FavoriteNode[] = [];
  const seen = new Set<string>();
  let folderCount = 0;

  const takeLink = (value: unknown): FavoriteLink | null => {
    // A bare string is the shape written before the bar held anything but
    // authors; a link carries its own id, label and (for a post) tweet id.
    if (typeof value === "string") {
      return value && !seen.has(`u:${value}`) && seen.size < MAX_PINNED_USERS
        ? (seen.add(`u:${value}`), userLink(value))
        : null;
    }
    const link = value as Partial<FavoriteLink>;
    const username = typeof link?.username === "string" ? link.username : "";
    const postId = typeof link?.postId === "string" ? link.postId : "";
    if (!username && !postId) return null;
    const id = postId ? `p:${postId}` : `u:${username}`;
    if (seen.has(id) || seen.size >= MAX_PINNED_USERS) return null;
    seen.add(id);
    return postId
      ? postLink(
          postId,
          username,
          typeof link.hint === "string" ? link.hint : "",
          typeof link.from === "string" ? link.from : null,
          typeof link.q === "string" ? link.q : null,
        )
      : userLink(username);
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

export function readFavorites(scope: FavoritesScope): FavoriteNode[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(PINS_KEYS[scope]);
    if (!raw) return [];
    return parse(JSON.parse(raw) as unknown);
  } catch {
    return [];
  }
}

export function writeFavorites(
  scope: FavoritesScope,
  nodes: FavoriteNode[],
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PINS_KEYS[scope], JSON.stringify(nodes));
  } catch {
    // Private mode / blocked storage - the favorites stay in memory only.
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
 * ``nodes`` with ``link`` pinned or unpinned.
 *
 * A new favorite goes to the front of the bar, so the most recently pinned one
 * is the first chip; unpinning finds it wherever it was filed. The cap refuses
 * the new pin rather than silently dropping an older one out of a folder
 * someone organised.
 */
export function togglePinned(
  nodes: FavoriteNode[],
  link: FavoriteLink,
): FavoriteNode[] {
  if (isPinned(nodes, link.id)) return removeNode(nodes, link.id);
  if (listIds(nodes).length >= MAX_PINNED_USERS) return nodes;
  return [link, ...nodes];
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
 * Move a favorite to ``target`` - reordering the bar, filing an author into a
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
