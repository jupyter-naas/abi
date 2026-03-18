'use client';

import { usePathname } from 'next/navigation';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { getApiUrl } from '@/lib/config';

interface TenantConfig {
  apps: {
    name: string;
    url: string;
    description?: string | null;
    icon_emoji?: string | null;
  }[];
  tab_title: string;
  favicon_url: string | null;
  logo_url?: string | null;
  logo_rectangle_url?: string | null;
  logo_emoji?: string | null;
  primary_color: string;
  accent_color: string;
  background_color: string;
  font_family?: string | null;
  font_url?: string | null;
  login_card_max_width: string;
  login_card_padding: string;
  login_card_color: string;
  login_text_color?: string | null;
  login_input_color: string;
  login_border_radius: string;
  login_bg_image_url?: string | null;
  show_terms_footer: boolean;
  show_powered_by: boolean;
  login_footer_text?: string | null;
}

const DEFAULT_TENANT: TenantConfig = {
  apps: [],
  tab_title: 'ABI Nexus | naas.ai',
  favicon_url: null,
  logo_url: null,
  logo_rectangle_url: null,
  logo_emoji: null,
  primary_color: '#34D399',
  accent_color: '#1FA574',
  background_color: '#FFFFFF',
  font_family: null,
  font_url: null,
  login_card_max_width: '440px',
  login_card_padding: '2.5rem 3rem 3rem',
  login_card_color: '#FFFFFF',
  login_text_color: null,
  login_input_color: '#F4F4F4',
  login_border_radius: '0',
  login_bg_image_url: null,
  show_terms_footer: false,
  show_powered_by: true,
  login_footer_text: null,
};

const TenantContext = createContext<TenantConfig>(DEFAULT_TENANT);

export function useTenant() {
  return useContext(TenantContext);
}

/** Map workspace path segment to nav label for document title */
const WORKSPACE_SEGMENT_TITLE: Record<string, string> = {
  chat: 'Chat',
  search: 'Search',
  ontology: 'Ontology',
  graph: 'Knowledge Graph',
  files: 'Files',
  lab: 'Lab',
  apps: 'Apps',
  help: 'Help',
  settings: 'Workspace Settings',
  organization: 'Organization',
  account: 'Account',
};

function getPageTitle(pathname: string, tabTitle: string): string {
  // Auth routes and login: use config title only
  if (pathname.startsWith('/auth/') || pathname.startsWith('/org/')) {
    return tabTitle;
  }
  // First page (workspace chat root): use config title only
  const workspaceChatMatch = pathname.match(/^\/workspace\/[^/]+\/chat\/?$/);
  if (workspaceChatMatch) {
    return tabTitle;
  }
  // Other workspace routes: "Nav item | Config title"
  const workspaceMatch = pathname.match(/^\/workspace\/[^/]+\/([^/]+)/);
  if (workspaceMatch) {
    const segment = workspaceMatch[1].toLowerCase();
    const pageName = WORKSPACE_SEGMENT_TITLE[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
    return `${pageName} | ${tabTitle}`;
  }
  return tabTitle;
}

function applyFavicon(url: string) {
  const selectors = [
    'link[rel="icon"]',
    'link[rel="shortcut icon"]',
    'link[rel="apple-touch-icon"]',
  ];

  for (const sel of selectors) {
    const existing = document.querySelector(sel) as HTMLLinkElement | null;
    if (existing) {
      existing.href = url;
    } else {
      const link = document.createElement('link');
      link.rel = sel.includes('apple') ? 'apple-touch-icon' : 'icon';
      link.href = url;
      document.head.appendChild(link);
    }
  }
}

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [tenant, setTenant] = useState<TenantConfig>(DEFAULT_TENANT);
  const tenantFaviconUrlRef = useRef<string | null>(null);
  const pathnameRef = useRef(pathname);
  const tenantTabTitleRef = useRef(tenant.tab_title);
  pathnameRef.current = pathname;
  tenantTabTitleRef.current = tenant.tab_title;

  useEffect(() => {
    const apiBase = getApiUrl();
    fetch(`${apiBase}/api/tenant`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: Partial<TenantConfig> | null) => {
        if (!data) return;
        setTenant({
          ...DEFAULT_TENANT,
          ...data,
          apps: Array.isArray(data.apps) ? data.apps : [],
        });
      })
      .catch(() => {
        // Tenant endpoint unavailable — keep defaults
      });
  }, []);

  const applyTitleAndFavicon = () => {
    const title = getPageTitle(pathname, tenant.tab_title);
    document.title = title;
    if (tenant.favicon_url) {
      tenantFaviconUrlRef.current = tenant.favicon_url;
      applyFavicon(tenant.favicon_url);
    }
  };

  // Re-apply tenant title and favicon on every navigation so they persist
  // over route-level metadata (e.g. auth layout "Sign In").
  // Use multiple delays so we win after Next.js metadata on heavy routes (e.g. chat).
  useEffect(() => {
    applyTitleAndFavicon();
    const t1 = setTimeout(applyTitleAndFavicon, 100);
    const t2 = setTimeout(applyTitleAndFavicon, 300);
    const t3 = setTimeout(applyTitleAndFavicon, 600);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [tenant.tab_title, tenant.favicon_url, pathname]);

  // Keep favicon and title persistent: re-apply when something else (e.g. Next.js) changes the icon
  useEffect(() => {
    if (!tenant.favicon_url || typeof document === 'undefined') return;
    tenantFaviconUrlRef.current = tenant.favicon_url;

    const observer = new MutationObserver(() => {
      const icon = document.querySelector('link[rel="icon"]') as HTMLLinkElement | null;
      const faviconWrong = icon && tenantFaviconUrlRef.current && icon.href !== tenantFaviconUrlRef.current;
      if (faviconWrong) {
        const title = getPageTitle(pathnameRef.current, tenantTabTitleRef.current);
        document.title = title;
        if (tenantFaviconUrlRef.current) applyFavicon(tenantFaviconUrlRef.current);
      }
    });

    observer.observe(document.head, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['href'],
    });
    return () => observer.disconnect();
  }, [tenant.favicon_url, tenant.tab_title]);

  return (
    <TenantContext.Provider value={tenant}>{children}</TenantContext.Provider>
  );
}
