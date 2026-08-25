/**
 * Generated from `config.yaml` — do not edit.
 *
 * Regenerate with:
 *   uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.app_config --write
 * (`pnpm build` and `pnpm dev` do it for you.)
 *
 * This is data only. The lookups the components use are in `lib/appConfig.ts`.
 */

/** Every configured page, visible or not — what the components switch on. */
export type PageKey = "search" | "count" | "users" | "parameters";

export type SectionKey = "posts" | "users" | "parameters";

/** Rail icons drawn by `Shell.tsx`. */
export type IconName = "posts" | "users" | "gear";

export type PageConfig = {
  key: PageKey;
  label: string;
  path: string;
  visible: boolean;
  /** Whether the Scenario / Query dropdowns show on this page. */
  filters: boolean;
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
  favorites: boolean;
  pages: PageConfig[];
};

export const APP_NAME = "X Proxy";

/** Top-bar heading, with `{app}` / `{section}` placeholders. */
export const APP_TITLE = "{app} - {section}";

/** Where `/` sends a visitor who named no page. */
export const DEFAULT_PAGE: PageKey = "count";

export const FAVORITES_LIMITS = {
  maxUsers: 60,
  maxFolders: 12,
  maxFolderName: 32,
};

/** The author feed on the Users page. */
export const FEED = {
  /** Posts the feed opens with, and each "show more" adds. */
  batch: 10,
};

export const SECTIONS: SectionConfig[] = [
  {
    "key": "posts",
    "label": "Posts",
    "icon": "posts",
    "visible": true,
    "place": "main",
    "topNav": true,
    "favorites": false,
    "pages": [
      {
        "key": "search",
        "label": "Search Recent Tweets",
        "path": "/posts/search-posts-recent/",
        "visible": true,
        "filters": true
      },
      {
        "key": "count",
        "label": "Count Recent Tweets",
        "path": "/posts/get-posts-counts-recent/",
        "visible": true,
        "filters": true
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
    "favorites": true,
    "pages": [
      {
        "key": "users",
        "label": "Search Users",
        "path": "/users/search",
        "visible": true,
        "filters": false
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
    "favorites": false,
    "pages": [
      {
        "key": "parameters",
        "label": "Parameters",
        "path": "/parameters/",
        "visible": true,
        "filters": false
      }
    ]
  }
];
