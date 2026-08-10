"use client";

import Link from "next/link";
import { useAppState } from "@/components/AppProvider";
import { hrefFor } from "@/lib/routes";
import type { PageKey } from "@/lib/types";

const TITLES: Record<PageKey, string> = {
  count: "Count Recent Tweets",
  search: "Search Recent Tweets",
  users: "Search Users",
  parameters: "Parameters",
};

type Section = "posts" | "users" | "parameters";

const SECTION_OF: Record<PageKey, Section> = {
  count: "posts",
  search: "posts",
  users: "users",
  parameters: "parameters",
};

/** Subpages listed in the second bar, per section. */
const SUBPAGES: Record<Section, { key: PageKey; label: string }[]> = {
  posts: [
    { key: "count", label: "Count Recent Tweets" },
    { key: "search", label: "Search Recent Tweets" },
  ],
  users: [{ key: "users", label: "Search Users" }],
  parameters: [],
};

const SECTION_LABELS: Record<Section, string> = {
  posts: "Posts",
  users: "Users",
  parameters: "Parameters",
};

type Props = {
  page: PageKey;
  /** Href of another page, carrying over the state that page honours. */
  hrefOf: (page: PageKey) => string;
  builtAt: string | null;
  filters: React.ReactNode;
  children: React.ReactNode;
  /** Author currently open, so the sidebar can mark its pin as active. */
  activeUser?: string | null;
  /**
   * Opens an author (or closes the open one, with ``null``) from the sidebar.
   *
   * Needed because a link that only changes the query string of the page you
   * are already on is not a route change: Next keeps the same component
   * mounted and fires no popstate, so the view would never hear about it.
   * From another page the link navigates for real and this is not used.
   */
  onOpenUser?: (username: string | null) => void;
};

export function Shell({
  page,
  hrefOf,
  builtAt,
  filters,
  children,
  activeUser = null,
  onOpenUser,
}: Props) {
  // Collapse, last-subpage and pins all outlive a page change, so they live in
  // the provider the layout keeps mounted rather than in this component.
  const {
    postsPage,
    sidebarCollapsed: collapsed,
    toggleSidebar,
    pinnedUsers,
    togglePinnedUser,
  } = useAppState();
  const section = SECTION_OF[page];
  const subpages = SUBPAGES[section];

  /**
   * Handles a Users link while the Users page is already open.
   *
   * Modified clicks (new tab, new window) are left to the browser, and from any
   * other page the click falls through to Next's own navigation.
   */
  const openUser =
    (username: string | null) => (event: React.MouseEvent<HTMLAnchorElement>) => {
      if (
        page !== "users" ||
        !onOpenUser ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      event.preventDefault();
      onOpenUser(username);
    };

  return (
    <div className="app">
      <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
        <div
          className="brand"
          onClick={toggleSidebar}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") toggleSidebar();
          }}
        >
          <svg className="brand-ico" viewBox="0 0 24 24" aria-hidden>
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
          <span className="brand-name">X / Twitter</span>
          <span className="brand-toggle">{collapsed ? "▸" : "◂"}</span>
        </div>
        <nav className="nav nav-main">
          <Link
            className={`nav-item${section === "posts" ? " active" : ""}`}
            href={hrefOf(postsPage)}
          >
            <svg className="nav-ico" viewBox="0 0 24 24" aria-hidden>
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M7 9h10M7 13h10M7 17h5" />
            </svg>
            <span className="nav-label">Posts</span>
          </Link>
          <Link
            className={`nav-item${section === "users" ? " active" : ""}`}
            href={hrefOf("users")}
            onClick={openUser(null)}
          >
            <svg className="nav-ico" viewBox="0 0 24 24" aria-hidden>
              <circle cx="9" cy="8" r="3.5" />
              <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
              <path d="M16 5.2a3.5 3.5 0 0 1 0 5.6M17.5 14.2A6.5 6.5 0 0 1 21.5 20" />
            </svg>
            <span className="nav-label">Users</span>
          </Link>
        </nav>
        <nav className="nav nav-bottom">
          <Link
            className={`nav-item${page === "parameters" ? " active" : ""}`}
            href={hrefOf("parameters")}
          >
            <svg className="nav-ico" viewBox="0 0 24 24" aria-hidden>
              <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" />
              <path d="M19.4 13a7.8 7.8 0 0 0 .1-2l2-1.5-2-3.5-2.4 1a7.6 7.6 0 0 0-1.7-1l-.3-2.5H9.9l-.3 2.5a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5a7.8 7.8 0 0 0 .1 2l-2 1.5 2 3.5 2.4-1a7.6 7.6 0 0 0 1.7 1l.3 2.5h4.2l.3-2.5a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.5-2-1.5z" />
            </svg>
            <span className="nav-label">Parameters</span>
          </Link>
        </nav>
      </aside>
      {subpages.length ? (
        <aside className="subsidebar">
          <div className="subsidebar-head">{SECTION_LABELS[section]}</div>
          <nav className="subnav">
            {subpages.map((sub) => (
              <Link
                key={sub.key}
                className={`subnav-item${page === sub.key ? " active" : ""}`}
                href={hrefOf(sub.key)}
              >
                {sub.label}
              </Link>
            ))}
          </nav>
          {/* Pins sit under the Users subpages: they are shortcuts into that
              section, so they show where its own navigation lives. */}
          {section === "users" && pinnedUsers.length ? (
            <nav className="subnav subnav-pinned" aria-label="Pinned users">
              <div className="subnav-head">Pinned</div>
              {pinnedUsers.map((username) => (
                <div className="pin-row" key={username}>
                  <Link
                    className={`subnav-item pin-item${
                      username === activeUser ? " active" : ""
                    }`}
                    href={hrefFor("users", { user: username })}
                    onClick={openUser(username)}
                  >
                    <span className="pin-avatar" aria-hidden>
                      {username.slice(0, 1).toUpperCase()}
                    </span>
                    <span className="pin-handle">@{username}</span>
                  </Link>
                  <button
                    type="button"
                    className="pin-remove"
                    title={`Unpin @${username}`}
                    aria-label={`Unpin @${username}`}
                    onClick={() => togglePinnedUser(username)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </nav>
          ) : null}
        </aside>
      ) : null}
      <div className="main">
        <div className="main-head">
          <div className="topnav">
            <h1>{TITLES[page]}</h1>
            {builtAt ? (
              <span className="built">Snapshot · {builtAt}</span>
            ) : null}
          </div>
          {filters}
        </div>
        {children}
      </div>
    </div>
  );
}
