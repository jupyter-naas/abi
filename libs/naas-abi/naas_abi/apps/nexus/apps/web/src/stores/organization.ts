/**
 * Organization store for NEXUS.
 * Manages organization branding (public, pre-auth) and org membership (authed).
 */

import { create } from 'zustand';
import { getApiUrl } from '@/lib/config';
import { authFetch } from './auth';

const getApiBase = () => getApiUrl();
const normalize = (url?: string | null) =>
  (url && url.startsWith('/') ? `${getApiBase()}${url}` : url || undefined);

export interface OrganizationBranding {
  id: string;
  name: string;
  slug: string;
  logoUrl?: string;              // Square logo (icon, sidebar, compact)
  logoRectangleUrl?: string;      // Wide/horizontal logo (login page, headers)
  logoEmoji?: string;
  primaryColor: string;
  accentColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  fontUrl?: string;               // CSS/Typekit URL to load custom font
  loginCardMaxWidth?: string;     // e.g. "440px"
  loginCardPadding?: string;      // e.g. "2.5rem 3rem 3rem"
  loginCardColor?: string;        // Card background (e.g. #ffffff)
  loginTextColor?: string;        // Text color on card (e.g. #1a1a1a)
  loginInputColor?: string;       // Input background color (e.g. #F4F4F4)
  loginBorderRadius?: string;     // Border radius in px (e.g. "0" for sharp)
  loginBgImageUrl?: string;       // Background image URL
  showTermsFooter: boolean;
  showPoweredBy: boolean;
  loginFooterText?: string;       // Custom footer line (e.g. "© 2026 Forvis Mazars - Confidentiel")
  secondaryLogoUrl?: string;       // Second logo for dual-logo layout
  showLogoSeparator: boolean;      // Vertical bar between primary and secondary logo
  defaultTheme?: string;           // "light", "dark", or undefined (system)
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  ownerId: string;
  logoUrl?: string;
  logoRectangleUrl?: string;
  logoEmoji?: string;
  primaryColor?: string;
  accentColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  fontUrl?: string;
  loginCardMaxWidth?: string;
  loginCardPadding?: string;
  loginCardColor?: string;
  loginTextColor?: string;
  loginInputColor?: string;
  loginBorderRadius?: string;
  loginBgImageUrl?: string;
  showTermsFooter?: boolean;
  showPoweredBy?: boolean;
  loginFooterText?: string;
  secondaryLogoUrl?: string;
  showLogoSeparator?: boolean;
  defaultTheme?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface OrganizationMember {
  id: string;
  organizationId: string;
  userId: string;
  role: 'owner' | 'admin' | 'member';
  email?: string;
  name?: string;
  createdAt?: string;
}

interface OrganizationState {
  // Branding (public, cached by slug)
  brandingCache: Record<string, OrganizationBranding>;
  brandingLoading: boolean;
  brandingError: string | null;

  // User's organizations (authed)
  organizations: Organization[];
  currentOrgSlug: string | null;

  // Organization members
  membersCache: Record<string, OrganizationMember[]>;
  membersLoading: boolean;

  // Actions
  fetchBranding: (slug: string) => Promise<OrganizationBranding | null>;
  getBranding: (slug: string) => OrganizationBranding | null;
  fetchOrganizations: () => Promise<void>;
  updateOrganization: (orgId: string, updates: Partial<Organization>) => Promise<Organization | null>;
  setCurrentOrgSlug: (slug: string | null) => void;
  
  // Member actions
  fetchMembers: (orgId: string) => Promise<OrganizationMember[]>;
  inviteMember: (orgId: string, email: string, role: 'admin' | 'member') => Promise<OrganizationMember | null>;
  updateMemberRole: (orgId: string, userId: string, role: 'owner' | 'admin' | 'member') => Promise<OrganizationMember | null>;
  removeMember: (orgId: string, userId: string) => Promise<boolean>;
}

export const useOrganizationStore = create<OrganizationState>()((set, get) => ({
  brandingCache: {},
  brandingLoading: false,
  brandingError: null,
  organizations: [],
  currentOrgSlug: null,
  membersCache: {},
  membersLoading: false,

  fetchBranding: async (slug: string): Promise<OrganizationBranding | null> => {
    // Return from cache if available
    const cached = get().brandingCache[slug];
    if (cached) return cached;

    set({ brandingLoading: true, brandingError: null });

    try {
      // Public endpoint - no auth needed
      const response = await fetch(`${getApiBase()}/api/organizations/slug/${slug}/branding`);

      if (!response.ok) {
        if (response.status === 404) {
          set({ brandingLoading: false, brandingError: 'Organization not found' });
          return null;
        }
        throw new Error('Failed to fetch branding');
      }

      const data = await response.json();

      const branding: OrganizationBranding = {
        id: data.id,
        name: data.name,
        slug: data.slug,
        logoUrl: normalize(data.logo_url),
        logoRectangleUrl: normalize(data.logo_rectangle_url),
        logoEmoji: data.logo_emoji,
        primaryColor: data.primary_color || '#34D399',
        accentColor: data.accent_color,
        backgroundColor: data.background_color,
        fontFamily: data.font_family,
        fontUrl: data.font_url || undefined,
        loginCardMaxWidth: data.login_card_max_width || undefined,
        loginCardPadding: data.login_card_padding || undefined,
        loginCardColor: data.login_card_color,
        loginTextColor: data.login_text_color,
        loginInputColor: data.login_input_color,
        loginBorderRadius: data.login_border_radius,
        loginBgImageUrl: normalize(data.login_bg_image_url),
        showTermsFooter: data.show_terms_footer ?? true,
        showPoweredBy: data.show_powered_by ?? true,
        loginFooterText: data.login_footer_text || undefined,
        secondaryLogoUrl: normalize(data.secondary_logo_url) || undefined,
        showLogoSeparator: data.show_logo_separator ?? false,
        defaultTheme: data.default_theme || undefined,
      };

      set((state) => ({
        brandingCache: { ...state.brandingCache, [slug]: branding },
        brandingLoading: false,
        brandingError: null,
      }));

      return branding;
    } catch (error) {
      set({
        brandingLoading: false,
        brandingError: error instanceof Error ? error.message : 'Failed to fetch branding',
      });
      return null;
    }
  },

  getBranding: (slug: string): OrganizationBranding | null => {
    return get().brandingCache[slug] || null;
  },

  fetchOrganizations: async (): Promise<void> => {
    try {
      const response = await authFetch('/api/organizations');
      if (!response.ok) {
        console.error('Failed to fetch organizations:', response.status);
        return;
      }
      const data = await response.json();

      const organizations: Organization[] = data.map((org: any) => ({
        id: org.id,
        name: org.name,
        slug: org.slug,
        ownerId: org.owner_id,
        logoUrl: normalize(org.logo_url),
        logoRectangleUrl: normalize(org.logo_rectangle_url),
        logoEmoji: org.logo_emoji,
        primaryColor: org.primary_color,
        accentColor: org.accent_color,
        backgroundColor: org.background_color,
        fontFamily: org.font_family,
        fontUrl: org.font_url || undefined,
        loginCardMaxWidth: org.login_card_max_width || undefined,
        loginCardPadding: org.login_card_padding || undefined,
        loginCardColor: org.login_card_color,
        loginTextColor: org.login_text_color,
        loginInputColor: org.login_input_color,
        loginBorderRadius: org.login_border_radius,
        loginBgImageUrl: normalize(org.login_bg_image_url),
        showTermsFooter: org.show_terms_footer ?? true,
        showPoweredBy: org.show_powered_by ?? true,
        loginFooterText: org.login_footer_text || undefined,
        secondaryLogoUrl: normalize(org.secondary_logo_url) || undefined,
        showLogoSeparator: org.show_logo_separator ?? false,
        defaultTheme: org.default_theme || undefined,
        createdAt: org.created_at,
        updatedAt: org.updated_at,
      }));

      set({ organizations });
    } catch (error) {
      console.error('Failed to fetch organizations:', error);
    }
  },

  updateOrganization: async (orgId: string, updates: Partial<Organization>): Promise<Organization | null> => {
    try {
      // Convert camelCase to snake_case for API
      const apiUpdates: Record<string, any> = {};
      const keyMap: Record<string, string> = {
        name: 'name', slug: 'slug', logoUrl: 'logo_url', logoRectangleUrl: 'logo_rectangle_url',
        logoEmoji: 'logo_emoji', primaryColor: 'primary_color', accentColor: 'accent_color',
        backgroundColor: 'background_color', fontFamily: 'font_family',
        fontUrl: 'font_url', loginCardMaxWidth: 'login_card_max_width',
        loginCardPadding: 'login_card_padding', loginCardColor: 'login_card_color', loginTextColor: 'login_text_color',
        loginInputColor: 'login_input_color', loginBorderRadius: 'login_border_radius',
        loginBgImageUrl: 'login_bg_image_url', showTermsFooter: 'show_terms_footer',
        showPoweredBy: 'show_powered_by', loginFooterText: 'login_footer_text',
        secondaryLogoUrl: 'secondary_logo_url', showLogoSeparator: 'show_logo_separator',
        defaultTheme: 'default_theme',
      };
      for (const [key, value] of Object.entries(updates)) {
        const apiKey = keyMap[key];
        if (apiKey) apiUpdates[apiKey] = value;
      }

      const response = await authFetch(`/api/organizations/${orgId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiUpdates),
      });
      if (!response.ok) {
        console.error('Failed to update organization:', response.status);
        return null;
      }
      const org = await response.json();
      const updated: Organization = {
        id: org.id, name: org.name, slug: org.slug, ownerId: org.owner_id,
        logoUrl: normalize(org.logo_url), logoRectangleUrl: normalize(org.logo_rectangle_url),
        logoEmoji: org.logo_emoji, primaryColor: org.primary_color,
        accentColor: org.accent_color, backgroundColor: org.background_color,
        fontFamily: org.font_family, fontUrl: org.font_url || undefined,
        loginCardMaxWidth: org.login_card_max_width || undefined,
        loginCardPadding: org.login_card_padding || undefined,
        loginCardColor: org.login_card_color,
        loginTextColor: org.login_text_color, loginInputColor: org.login_input_color,
        loginBorderRadius: org.login_border_radius, loginBgImageUrl: org.login_bg_image_url,
        showTermsFooter: org.show_terms_footer ?? true, showPoweredBy: org.show_powered_by ?? true,
        loginFooterText: org.login_footer_text || undefined,
        secondaryLogoUrl: normalize(org.secondary_logo_url) || undefined,
        showLogoSeparator: org.show_logo_separator ?? false,
        defaultTheme: org.default_theme || undefined,
        createdAt: org.created_at, updatedAt: org.updated_at,
      };

      // Update in local state
      set((state) => ({
        organizations: state.organizations.map((o) => o.id === orgId ? updated : o),
        // Invalidate branding cache for this org's slug
        brandingCache: Object.fromEntries(
          Object.entries(state.brandingCache).filter(([key]) => key !== updated.slug)
        ),
      }));

      return updated;
    } catch (error) {
      console.error('Failed to update organization:', error);
      return null;
    }
  },

  setCurrentOrgSlug: (slug: string | null) => {
    set({ currentOrgSlug: slug });
  },

  fetchMembers: async (orgId: string): Promise<OrganizationMember[]> => {
    set({ membersLoading: true });

    try {
      const response = await authFetch(`/api/organizations/${orgId}/members`);
      if (!response.ok) {
        console.error('Failed to fetch members:', response.status);
        set({ membersLoading: false });
        return [];
      }
      const data = await response.json();

      const members: OrganizationMember[] = data.map((m: any) => ({
        id: m.id,
        organizationId: m.organization_id,
        userId: m.user_id,
        role: m.role,
        email: m.email,
        name: m.name,
        createdAt: m.created_at,
      }));

      set((state) => ({
        membersCache: { ...state.membersCache, [orgId]: members },
        membersLoading: false,
      }));

      return members;
    } catch (error) {
      console.error('Failed to fetch members:', error);
      set({ membersLoading: false });
      return [];
    }
  },

  inviteMember: async (orgId: string, email: string, role: 'admin' | 'member'): Promise<OrganizationMember | null> => {
    try {
      const response = await authFetch(`/api/organizations/${orgId}/members/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, role }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to invite member');
      }
      const data = await response.json();

      const member: OrganizationMember = {
        id: data.id,
        organizationId: data.organization_id,
        userId: data.user_id,
        role: data.role,
        email: data.email,
        name: data.name,
        createdAt: data.created_at,
      };

      // Update cache
      set((state) => {
        const currentMembers = state.membersCache[orgId] || [];
        return {
          membersCache: {
            ...state.membersCache,
            [orgId]: [...currentMembers, member],
          },
        };
      });

      return member;
    } catch (error) {
      console.error('Failed to invite member:', error);
      throw error;
    }
  },

  updateMemberRole: async (orgId: string, userId: string, role: 'owner' | 'admin' | 'member'): Promise<OrganizationMember | null> => {
    try {
      const response = await authFetch(`/api/organizations/${orgId}/members/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to update member role');
      }
      const data = await response.json();

      const member: OrganizationMember = {
        id: data.id,
        organizationId: data.organization_id,
        userId: data.user_id,
        role: data.role,
        email: data.email,
        name: data.name,
        createdAt: data.created_at,
      };

      // Update cache
      set((state) => {
        const currentMembers = state.membersCache[orgId] || [];
        return {
          membersCache: {
            ...state.membersCache,
            [orgId]: currentMembers.map((m) =>
              m.userId === userId ? member : m
            ),
          },
        };
      });

      return member;
    } catch (error) {
      console.error('Failed to update member role:', error);
      throw error;
    }
  },

  removeMember: async (orgId: string, userId: string): Promise<boolean> => {
    try {
      const response = await authFetch(`/api/organizations/${orgId}/members/${userId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to remove member');
      }

      // Update cache
      set((state) => {
        const currentMembers = state.membersCache[orgId] || [];
        return {
          membersCache: {
            ...state.membersCache,
            [orgId]: currentMembers.filter((m) => m.userId !== userId),
          },
        };
      });

      return true;
    } catch (error) {
      console.error('Failed to remove member:', error);
      throw error;
    }
  },
}));
