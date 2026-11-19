"use client";

import Link from "next/link";
import { useAppState } from "@/components/AppProvider";
import { FavoritesBar } from "@/components/FavoritesBar";
import {
  APP_NAME,
  favoritesOn,
  railSections,
  sectionOf,
  tabOf,
  tabsOf,
  titleOf,
} from "@/lib/appConfig";
import type { IconName, SectionConfig } from "@/lib/appConfig";
import type { PageKey } from "@/lib/types";

/**
 * The rail icons a section may ask for by name in `config.yaml`.
 *
 * The drawing stays here - a config file is no place for path data - so adding
 * an icon means adding it to this map and to `ICONS` in `app_config.py`.
 */
const ICONS: Record<IconName, React.ReactNode> = {
  posts: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 9h10M7 13h10M7 17h5" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M16 5.2a3.5 3.5 0 0 1 0 5.6M17.5 14.2A6.5 6.5 0 0 1 21.5 20" />
    </>
  ),
  gear: (
    <>
      <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" />
      <path d="M19.4 13a7.8 7.8 0 0 0 .1-2l2-1.5-2-3.5-2.4 1a7.6 7.6 0 0 0-1.7-1l-.3-2.5H9.9l-.3 2.5a7.6 7.6 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5a7.8 7.8 0 0 0 .1 2l-2 1.5 2 3.5 2.4-1a7.6 7.6 0 0 0 1.7 1l.3 2.5h4.2l.3-2.5a7.6 7.6 0 0 0 1.7-1l2.4 1 2-3.5-2-1.5z" />
    </>
  ),
};

type Props = {
  page: PageKey;
  /** Href of another page, carrying over the state that page honours. */
  hrefOf: (page: PageKey) => string;
  /** Stamp of the publish every page is reading, shown at the foot of the rail. */
  builtAt: string | null;
  filters: React.ReactNode;
  children: React.ReactNode;
  /** Author currently open, so the Users links can be intercepted. */
  activeUser?: string | null;
  /** Id of the favorite this page is showing, so its chip reads as active. */
  activeFavorite?: string | null;
  /**
   * Opens an author (or closes the open one, with ``null``) from the chrome.
   *
   * Needed because a link that only changes the query string of the page you
   * are already on is not a route change: Next keeps the same component
   * mounted and fires no popstate, so the view would never hear about it.
   * From another page the link navigates for real and this is not used.
   */
  onOpenUser?: (username: string | null) => void;
};

/**
 * The app chrome: section rail, then a browser-shaped header.
 *
 * What it lists - sections, their pages, their order, what is visible, which
 * section shows a title bar or the favorites bar - all comes from `config.yaml`
 * at the app root, by way of `lib/appConfig`.
 *
 * The header stacks the way a browser window does - the app and section name on
 * top, the section's pages as tabs under it, then the favorites bar on Users -
 * so the only rail left is the one that switches sections. Everything in it is
 * sticky: moving between tabs and favorites never means scrolling back up.
 */
export function Shell({
  page,
  hrefOf,
  builtAt,
  filters,
  children,
  activeUser = null,
  activeFavorite = null,
  onOpenUser,
}: Props) {
  // Collapse, last-subpage and favorites all outlive a page change, so they
  // live in the provider the layout keeps mounted rather than in this component.
  const {
    sectionPages,
    sidebarCollapsed: collapsed,
    toggleSidebar,
  } = useAppState();
  const section = sectionOf(page);
  const tabs = tabsOf(section.key);
  // A page that is not a tab keeps another one lit - the post page keeps
  // Search Tweets lit, the way an author's page keeps Search Users lit.
  const activeTab = tabOf(page);
  const favorites = favoritesOn(page);

  /**
   * One rail entry.
   *
   * A section link goes to the page last visited in it, so coming back to Posts
   * lands where it was left. Users is intercepted while the Users page is
   * already open (see `openUser`), since that is a param change, not a route.
   */
  const railLink = (entry: SectionConfig) => (
    <Link
      key={entry.key}
      className={`nav-item${section.key === entry.key ? " active" : ""}`}
      href={hrefOf(sectionPages[entry.key])}
      onClick={entry.key === "users" ? openUser(null) : undefined}
    >
      <svg className="nav-ico" viewBox="0 0 24 24" aria-hidden>
        {ICONS[entry.icon]}
      </svg>
      <span className="nav-label">{entry.label}</span>
    </Link>
  );

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

  /**
   * A tab click opens that tab's page. When the tab is already lit because a
   * detail page belongs under it (a post keeps Search Tweets active), the
   * link still navigates to the tab route. On Users, clicking Search Users
   * again closes the open author instead of doing nothing.
   */
  const onTabClick =
    (tabKey: PageKey) => (event: React.MouseEvent<HTMLAnchorElement>) => {
      if (
        page === tabKey &&
        tabKey === "users" &&
        activeUser &&
        onOpenUser &&
        event.button === 0 &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        !event.altKey &&
        !event.defaultPrevented
      ) {
        event.preventDefault();
        onOpenUser(null);
      }
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
          <span className="brand-name">{APP_NAME}</span>
          <span className="brand-toggle">{collapsed ? "▸" : "◂"}</span>
        </div>
        <nav className="nav nav-main">{railSections("main").map(railLink)}</nav>
        {/* Pinned to the foot of the rail: the snapshot the whole app is
            reading, then the rule, then Parameters. */}
        <div className="sidebar-foot">
          {builtAt ? (
            <div className="sidebar-built" title={`Snapshot · ${builtAt}`}>
              Snapshot · {builtAt}
            </div>
          ) : null}
          {railSections("bottom").length ? (
            <nav className="nav nav-bottom">
              {railSections("bottom").map(railLink)}
            </nav>
          ) : null}
        </div>
      </aside>
      <div className="main">
        <div className="main-head">
          {/* A section can drop the title bar (`top_nav: false`) when its page
              carries a heading of its own. */}
          {section.topNav ? (
            <div className="topnav">
              <h1>{titleOf(section.key)}</h1>
            </div>
          ) : null}
          {/* No rule under the tabs when the favorites bar follows them: two
              lines that close nothing between them read as a seam. */}
          <nav
            className={`tabstrip${favorites !== "none" ? " joined" : ""}`}
            aria-label={`${section.label} pages`}
          >
            {tabs.map((tab) => (
              <Link
                key={tab.key}
                className={`tab${activeTab === tab.key ? " active" : ""}`}
                href={hrefOf(tab.key)}
                aria-current={activeTab === tab.key ? "page" : undefined}
                onClick={onTabClick(tab.key)}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
          {/* Configured per section, and per page where a page differs: the
              chips are jumps to an author, so they show where authors are. */}
          {favorites !== "none" ? (
            <FavoritesBar
              scope={favorites}
              activeId={activeFavorite}
              openUser={openUser}
            />
          ) : null}
          {filters}
        </div>
        {children}
      </div>
    </div>
  );
}
