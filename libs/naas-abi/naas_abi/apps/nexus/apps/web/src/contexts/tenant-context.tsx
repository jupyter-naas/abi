'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { getApiUrl } from '@/lib/config';

interface TenantConfig {
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
  const [tenant, setTenant] = useState<TenantConfig>(DEFAULT_TENANT);

  useEffect(() => {
    const apiBase = getApiUrl();
    fetch(`${apiBase}/api/tenant`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: TenantConfig | null) => {
        if (!data) return;
        setTenant(data);
        document.title = data.tab_title;
        if (data.favicon_url) {
          applyFavicon(data.favicon_url);
        }
      })
      .catch(() => {
        // Tenant endpoint unavailable — keep defaults
      });
  }, []);

  return (
    <TenantContext.Provider value={tenant}>{children}</TenantContext.Provider>
  );
}
