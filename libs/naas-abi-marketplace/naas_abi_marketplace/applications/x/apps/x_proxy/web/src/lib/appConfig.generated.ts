/**
 * Generated from `config.yaml` - do not edit.
 *
 * Regenerate with:
 *   uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.app_config --write
 * (`pnpm build` and `pnpm dev` do it for you.)
 *
 * This is data only. The lookups the components use are in `lib/appConfig.ts`.
 */

/** Every configured page, visible or not - what the components switch on. */
export type PageKey = "tweets" | "search" | "post" | "count" | "users" | "parameters";

export type SectionKey = "posts" | "users" | "parameters";

/** Rail icons drawn by `Shell.tsx`. */
export type IconName = "posts" | "users" | "gear";

/** Which favorites bar a section or page carries - pinned authors, or posts. */
export type FavoritesBar = "none" | "users" | "posts";

export type PageConfig = {
  key: PageKey;
  label: string;
  path: string;
  visible: boolean;
  /** Whether the Scenario / Query dropdowns show on this page. */
  filters: boolean;
  /** Whether the page has a search box, whose needle lives in `?q=`. */
  searchBox: boolean;
  /** Overrides the section's favorites bar for this page. `null` inherits. */
  favorites: FavoritesBar | null;
  /** Tab to light up while this page is open. `null` means the page itself. */
  tab: PageKey | null;
};

export type SectionConfig = {
  key: SectionKey;
  label: string;
  icon: IconName;
  visible: boolean;
  /** `main` is the top group of the rail, `bottom` the group under the rule. */
  place: "main" | "bottom";
  /** False hides the "<app> - <section>" bar while in this section. */
  topNav: boolean;
  /** Which favorites bar this section carries. The two never mix. */
  favorites: FavoritesBar;
  pages: PageConfig[];
};

export const APP_NAME = "X Proxy";

/** Top-bar heading, with `{app}` / `{section}` placeholders. */
export const APP_TITLE = "{app} - {section}";

/** Where `/` sends a visitor who named no page. */
export const DEFAULT_PAGE: PageKey = "tweets";

export const FAVORITES_LIMITS = {
  maxUsers: 60,
  maxFolders: 12,
  maxFolderName: 32,
};

/* `charts:` is deliberately absent: it shapes what the publisher writes, and
 * the browser never needs it. */

/** Results per page on the search pages - both page the same way. */
export const RESULTS = {
  perPage: 100,
};

/** The author feed on the Users page. */
export const FEED = {
  /** Posts the feed opens with, and each "show more" adds. */
  batch: 10,
  /** The feed's tabs, in the order they are shown. */
  tabs: [{"key": "all", "label": "All"}, {"key": "matched", "label": "Matched Query"}, {"key": "referenced", "label": "Referenced"}],
};

export const SECTIONS: SectionConfig[] = [
  {
    "key": "posts",
    "label": "Posts",
    "icon": "posts",
    "visible": true,
    "place": "main",
    "topNav": true,
    "favorites": "none",
    "pages": [
      {
        "key": "tweets",
        "label": "Search Tweets",
        "path": "/posts/search-tweets/",
        "visible": true,
        "filters": false,
        "searchBox": true,
        "favorites": "posts",
        "tab": null
      },
      {
        "key": "search",
        "label": "Search Recent Tweets",
        "path": "/posts/search-posts-recent/",
        "visible": true,
        "filters": true,
        "searchBox": false,
        "favorites": null,
        "tab": null
      },
      {
        "key": "post",
        "label": "Post",
        "path": "/posts/post/",
        "visible": false,
        "filters": false,
        "searchBox": false,
        "favorites": "posts",
        "tab": "tweets"
      },
      {
        "key": "count",
        "label": "Count Recent Tweets",
        "path": "/posts/get-posts-counts-recent/",
        "visible": true,
        "filters": true,
        "searchBox": false,
        "favorites": null,
        "tab": null
      }
    ]
  },
  {
    "key": "users",
    "label": "Users",
    "icon": "users",
    "visible": true,
    "place": "main",
    "topNav": true,
    "favorites": "users",
    "pages": [
      {
        "key": "users",
        "label": "Search Users",
        "path": "/users/search",
        "visible": true,
        "filters": false,
        "searchBox": true,
        "favorites": null,
        "tab": null
      }
    ]
  },
  {
    "key": "parameters",
    "label": "Parameters",
    "icon": "gear",
    "visible": true,
    "place": "bottom",
    "topNav": true,
    "favorites": "none",
    "pages": [
      {
        "key": "parameters",
        "label": "Parameters",
        "path": "/parameters/",
        "visible": true,
        "filters": false,
        "searchBox": false,
        "favorites": null,
        "tab": null
      }
    ]
  }
];
