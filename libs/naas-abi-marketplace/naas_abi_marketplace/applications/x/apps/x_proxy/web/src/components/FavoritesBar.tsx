"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAppState } from "@/components/AppProvider";
import {
  folders as foldersOf,
  MAX_FOLDER_NAME,
  MAX_FOLDERS,
  parentOf,
} from "@/lib/pins";
import type {
  DropTarget,
  FavoriteFolder,
  FavoriteLink,
  FavoriteNode,
} from "@/lib/pins";
import { hrefFor } from "@/lib/routes";

/** Builds the click handler for a favorite, given the author it opens. */
export type OpenUserHandler = (
  username: string,
) => (event: React.MouseEvent<HTMLAnchorElement>) => void;

type Props = {
  /** Author currently open, so its chip can be marked active. */
  activeUser: string | null;
  openUser: OpenUserHandler;
};

/** Only one popup is up at a time: a folder's contents, or a chip's menu. */
type Popup = { kind: "folder" | "menu"; id: string };

const POPUP_WIDTH = 232;

function initial(username: string): string {
  return username.slice(0, 1).toUpperCase();
}

/**
 * The favorites bar — pinned authors and the folders filing them.
 *
 * A browser bookmarks bar, in the app: chips sit under the tabs on every page,
 * a chip is either an author or a folder, and both can be dragged to reorder,
 * dropped on a folder to file them, or dragged back out. Everything the drag
 * does is also on each chip's menu, because a control that only answers to a
 * pointer is a control keyboard users do not have.
 */
export function FavoritesBar({ activeUser, openUser }: Props) {
  const {
    favorites,
    createFolder,
    renameFavoriteFolder,
    removeFavorite,
    moveFavorite,
  } = useAppState();

  const [popup, setPopup] = useState<Popup | null>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [editing, setEditing] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropAt, setDropAt] = useState<DropTarget | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const anchorRef = useRef<HTMLElement | null>(null);

  const folders = foldersOf(favorites);

  function openPopup(kind: Popup["kind"], id: string, anchor: HTMLElement) {
    anchorRef.current = anchor;
    setPopup((current) =>
      current && current.kind === kind && current.id === id
        ? null
        : { kind, id },
    );
  }

  function closePopup() {
    setPopup(null);
    anchorRef.current = null;
  }

  // Close on outside click / Escape, so the popups behave like menus.
  useEffect(() => {
    if (!popup && !editing) return;
    // Only the popup closes here: a rename commits on the input's own blur,
    // which this very click is about to fire.
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      setPopup(null);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setPopup(null);
      setEditing(null);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [popup, editing]);

  // The bar is inside a sticky header and scrolls sideways of its own, so the
  // popup is fixed-positioned against the viewport and re-anchored whenever
  // anything scrolls or resizes (capture phase catches the bar's own scroll).
  useEffect(() => {
    if (!popup) return;
    function place() {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPos({
        top: rect.bottom + 4,
        left: Math.max(
          8,
          Math.min(rect.left, window.innerWidth - POPUP_WIDTH - 8),
        ),
      });
    }
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [popup]);

  function addFolder() {
    const id = createFolder();
    if (!id) return;
    // Straight into its name: an unnamed "New folder" organises nothing.
    setPopup(null);
    setEditing(id);
  }

  function commitName(id: string, name: string) {
    renameFavoriteFolder(id, name);
    setEditing(null);
  }

  function move(id: string, target: DropTarget) {
    moveFavorite(id, target);
    closePopup();
  }

  function drop(event: React.DragEvent) {
    event.preventDefault();
    if (dragId && dropAt) moveFavorite(dragId, dropAt);
    setDragId(null);
    setDropAt(null);
  }

  /** The bar node after ``id`` — where "drop on the right half" inserts. */
  function nextOnBar(id: string): string | null {
    const at = favorites.findIndex((node) => node.id === id);
    return at < 0 ? null : favorites[at + 1]?.id || null;
  }

  /**
   * Where a drag currently hovering ``node`` would land.
   *
   * A folder takes the drop into itself when the pointer is over its middle;
   * its edges, like any author chip, mean "insert on the bar here".
   */
  function overChip(event: React.DragEvent, node: FavoriteNode) {
    if (!dragId || dragId === node.id) return;
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    if (
      node.kind === "folder" &&
      x > rect.width * 0.25 &&
      x < rect.width * 0.75
    ) {
      setDropAt({ into: "folder", folderId: node.id });
      return;
    }
    setDropAt({
      into: "bar",
      before: x > rect.width / 2 ? nextOnBar(node.id) : node.id,
    });
  }

  function dropClass(node: FavoriteNode): string {
    if (!dropAt) return "";
    if (dropAt.into === "folder") {
      return dropAt.folderId === node.id ? " fav-drop-into" : "";
    }
    if (dropAt.before === node.id) return " fav-drop-before";
    const last = favorites[favorites.length - 1];
    if (!dropAt.before && last?.id === node.id) return " fav-drop-after";
    return "";
  }

  function dragProps(id: string) {
    return {
      draggable: true,
      onDragStart: (event: React.DragEvent) => {
        setDragId(id);
        event.dataTransfer.effectAllowed = "move";
        // Firefox starts no drag at all without payload on the transfer.
        event.dataTransfer.setData("text/plain", id);
      },
      onDragEnd: () => {
        setDragId(null);
        setDropAt(null);
      },
    };
  }

  function nameInput(folder: FavoriteFolder) {
    return (
      <span className="fav-chip fav-chip-editing">
        <input
          className="fav-name-input"
          autoFocus
          defaultValue={folder.name}
          maxLength={MAX_FOLDER_NAME}
          aria-label="Folder name"
          onFocus={(event) => event.currentTarget.select()}
          onBlur={(event) => commitName(folder.id, event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") setEditing(null);
          }}
        />
      </span>
    );
  }

  function chipMenuButton(node: FavoriteNode) {
    const label =
      node.kind === "folder"
        ? `Options for folder ${node.name}`
        : `Options for @${node.username}`;
    return (
      <button
        type="button"
        className="fav-more"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={popup?.kind === "menu" && popup.id === node.id}
        onClick={(event) => openPopup("menu", node.id, event.currentTarget)}
      >
        ⋮
      </button>
    );
  }

  function renderLink(link: FavoriteLink) {
    return (
      <span
        className={`fav-slot${dropClass(link)}`}
        key={link.id}
        onDragOver={(event) => overChip(event, link)}
      >
        <Link
          className={`fav-chip${link.username === activeUser ? " active" : ""}`}
          href={hrefFor("users", { user: link.username })}
          onClick={openUser(link.username)}
          onContextMenu={(event) => {
            event.preventDefault();
            openPopup("menu", link.id, event.currentTarget);
          }}
          {...dragProps(link.id)}
        >
          <span className="fav-avatar" aria-hidden>
            {initial(link.username)}
          </span>
          <span className="fav-label">@{link.username}</span>
        </Link>
        {chipMenuButton(link)}
      </span>
    );
  }

  function renderFolder(folder: FavoriteFolder) {
    if (editing === folder.id) {
      return (
        <span className="fav-slot" key={folder.id}>
          {nameInput(folder)}
        </span>
      );
    }
    const open = popup?.kind === "folder" && popup.id === folder.id;
    return (
      <span
        className={`fav-slot${dropClass(folder)}`}
        key={folder.id}
        onDragOver={(event) => overChip(event, folder)}
      >
        <button
          type="button"
          className={`fav-chip fav-folder${open ? " active" : ""}`}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={(event) => openPopup("folder", folder.id, event.currentTarget)}
          onContextMenu={(event) => {
            event.preventDefault();
            openPopup("menu", folder.id, event.currentTarget);
          }}
          {...dragProps(folder.id)}
        >
          <svg className="fav-folder-ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M3 6.5h6l2 2.5h10v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18z" />
          </svg>
          <span className="fav-label">{folder.name}</span>
          <span className="fav-count">{folder.items.length}</span>
        </button>
        {chipMenuButton(folder)}
      </span>
    );
  }

  function renderFolderPopup(folder: FavoriteFolder) {
    return (
      <div
        className="fav-pop"
        role="menu"
        aria-label={folder.name}
        style={{ top: pos.top, left: pos.left, width: POPUP_WIDTH }}
        // Dropping anywhere on the open folder files the author into it.
        onDragOver={(event) => {
          if (!dragId || dragId === folder.id) return;
          event.preventDefault();
          setDropAt({ into: "folder", folderId: folder.id });
        }}
      >
        {folder.items.length ? (
          folder.items.map((item) => (
            <div className="fav-pop-row" key={item.id}>
              <Link
                className={`fav-pop-item${
                  item.username === activeUser ? " active" : ""
                }`}
                href={hrefFor("users", { user: item.username })}
                onClick={(event) => {
                  closePopup();
                  openUser(item.username)(event);
                }}
                {...dragProps(item.id)}
              >
                <span className="fav-avatar" aria-hidden>
                  {initial(item.username)}
                </span>
                <span className="fav-label">@{item.username}</span>
              </Link>
              <button
                type="button"
                className="fav-pop-out"
                title={`Move @${item.username} to the favorites bar`}
                aria-label={`Move @${item.username} to the favorites bar`}
                onClick={() => move(item.id, { into: "bar", before: null })}
              >
                ↥
              </button>
            </div>
          ))
        ) : (
          <p className="fav-pop-empty">
            Empty — drop a favorite here, or file one from its ⋮ menu.
          </p>
        )}
      </div>
    );
  }

  function renderMenu(node: FavoriteNode) {
    const style = { top: pos.top, left: pos.left, width: POPUP_WIDTH };
    if (node.kind === "folder") {
      return (
        <div className="fav-pop" role="menu" style={style}>
          <div className="fav-pop-head">{node.name}</div>
          <button
            type="button"
            className="fav-pop-action"
            onClick={() => {
              closePopup();
              setEditing(node.id);
            }}
          >
            Rename…
          </button>
          <button
            type="button"
            className="fav-pop-action"
            onClick={() => {
              removeFavorite(node.id);
              closePopup();
            }}
          >
            {node.items.length
              ? `Delete folder and ${node.items.length} favorite${
                  node.items.length > 1 ? "s" : ""
                }`
              : "Delete folder"}
          </button>
        </div>
      );
    }

    const parent = parentOf(favorites, node.id);
    return (
      <div className="fav-pop" role="menu" style={style}>
        <div className="fav-pop-head">@{node.username}</div>
        {parent ? (
          <button
            type="button"
            className="fav-pop-action"
            onClick={() => move(node.id, { into: "bar", before: null })}
          >
            Move to favorites bar
          </button>
        ) : null}
        {folders
          .filter((folder) => folder.id !== parent?.id)
          .map((folder) => (
            <button
              type="button"
              className="fav-pop-action"
              key={folder.id}
              onClick={() =>
                move(node.id, { into: "folder", folderId: folder.id })
              }
            >
              Move to “{folder.name}”
            </button>
          ))}
        <div className="fav-pop-sep" />
        <button
          type="button"
          className="fav-pop-action"
          onClick={() => {
            removeFavorite(node.id);
            closePopup();
          }}
        >
          Remove favorite
        </button>
      </div>
    );
  }

  const shown = popup
    ? favorites
        .flatMap<FavoriteNode>((node) =>
          node.kind === "folder" ? [node, ...node.items] : [node],
        )
        .find((node) => node.id === popup.id) || null
    : null;

  return (
    <div className="favbar" ref={rootRef} onDrop={drop}>
      <div
        className="favbar-items"
        role="navigation"
        aria-label="Favorites"
        onDragOver={(event) => {
          // Past the last chip: land at the end of the bar.
          if (!dragId || event.target !== event.currentTarget) return;
          event.preventDefault();
          setDropAt({ into: "bar", before: null });
        }}
      >
        {favorites.map((node) =>
          node.kind === "folder" ? renderFolder(node) : renderLink(node),
        )}
        {favorites.length ? null : (
          <span className="favbar-empty">
            Pin an author on Users to keep it here.
          </span>
        )}
      </div>
      <button
        type="button"
        className="favbar-add"
        title={
          folders.length >= MAX_FOLDERS
            ? `At most ${MAX_FOLDERS} folders`
            : "New folder"
        }
        disabled={folders.length >= MAX_FOLDERS}
        onClick={addFolder}
      >
        <svg className="fav-folder-ico" viewBox="0 0 24 24" aria-hidden>
          <path d="M3 6.5h6l2 2.5h10v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18z" />
          <path d="M14.5 13.5h4M16.5 11.5v4" />
        </svg>
        <span>New folder</span>
      </button>
      {popup && shown
        ? popup.kind === "folder"
          ? renderFolderPopup(shown as FavoriteFolder)
          : renderMenu(shown)
        : null}
    </div>
  );
}
