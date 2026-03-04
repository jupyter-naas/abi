'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { Sidebar } from './sidebar';
import { AIPane } from './ai-pane';
import { useWorkspaceStore } from '@/stores/workspace';
import { PresenceIndicator } from '@/components/presence-indicator';

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

// Convert hex to HSL for Tailwind CSS variables
function hexToHSL(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return '160 84% 45%'; // fallback to default primary
  
  let r = parseInt(result[1], 16) / 255;
  let g = parseInt(result[2], 16) / 255;
  let b = parseInt(result[3], 16) / 255;
  
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

export function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  // Subscribe to reactive state to trigger re-render on workspace change
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const toggleContextPanel = useWorkspaceStore((state) => state.toggleContextPanel);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const { setTheme } = useTheme();
  const [orgBorderRadius, setOrgBorderRadius] = useState('0');

  // Fetch workspaces on mount
  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  // Fetch org branding to get border radius AND theme
  useEffect(() => {
    const fetchOrgBranding = async () => {
      const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
      if (!currentWorkspace) return;
      
      // Check if user has explicitly overridden theme
      const hasUserOverride = localStorage.getItem('nexus-theme-user-override') === 'true';
      
      // Fetch workspace details to get organization_id
      try {
        const { authFetch } = await import('@/stores/auth');
        const wsResponse = await authFetch(`/api/workspaces/${currentWorkspaceId}`);
        if (wsResponse.ok) {
          const wsData = await wsResponse.json();
          if (wsData.organization_id) {
            // Fetch org branding
            const orgResponse = await authFetch(`/api/organizations/${wsData.organization_id}`);
            if (orgResponse.ok) {
              const orgData = await orgResponse.json();
              // Handle border radius - allow 0, only fallback if undefined/null
              const radius = orgData.loginBorderRadius ?? orgData.login_border_radius ?? '0';
              console.log('[WorkspaceLayout] Org border radius:', radius, 'from org:', wsData.organization_id);
              setOrgBorderRadius(radius);
              
              // Apply org theme ONLY if user hasn't explicitly overridden it
              if (!hasUserOverride) {
                const orgTheme = orgData.defaultTheme || orgData.default_theme;
                if (orgTheme && (orgTheme === 'light' || orgTheme === 'dark' || orgTheme === 'system')) {
                  console.log('[WorkspaceLayout] Applying org theme (no user override):', orgTheme);
                  setTheme(orgTheme);
                } else {
                  console.log('[WorkspaceLayout] No org theme set, defaulting to light');
                  // Default to light when org has no theme
                  setTheme('light');
                }
              } else {
                console.log('[WorkspaceLayout] User has overridden theme, skipping org theme');
              }
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch org branding:', error);
      }
    };

    if (currentWorkspaceId) {
      fetchOrgBranding();
    }

    // Listen for real-time theme changes from branding page
    const handleThemeChange = (event: CustomEvent) => {
      const newTheme = event.detail;
      console.log('[WorkspaceLayout] Theme change event:', newTheme);
      
      // Only apply if user hasn't overridden
      const hasUserOverride = localStorage.getItem('nexus-theme-user-override') === 'true';
      if (!hasUserOverride && newTheme && (newTheme === 'light' || newTheme === 'dark' || newTheme === 'system')) {
        setTheme(newTheme);
      }
    };

    window.addEventListener('org-theme-changed', handleThemeChange as EventListener);
    return () => window.removeEventListener('org-theme-changed', handleThemeChange as EventListener);
  }, [currentWorkspaceId]); // REMOVED workspaces and setTheme - they cause infinite loops

  // Fetch agents when workspace loads
  useEffect(() => {
    const loadAgents = async () => {
      if (currentWorkspaceId) {
        const { useAgentsStore } = await import('@/stores/agents');
        await useAgentsStore.getState().fetchAgents(currentWorkspaceId);
      }
    };
    loadAgents();
  }, [currentWorkspaceId]);

  // Keyboard shortcut: Cmd+K to toggle AI pane
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleContextPanel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleContextPanel]);
  
  // Find current workspace from state
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId);
  
  // Get theme colors with fallbacks
  const primaryColor = currentWorkspace?.theme?.primaryColor || '#22c55e';
  const accentColor = currentWorkspace?.theme?.accentColor || primaryColor;
  
  // Apply theme to document root for Tailwind CSS variables
  useEffect(() => {
    if (primaryColor && accentColor) {
      const root = document.documentElement;
      const primaryHSL = hexToHSL(primaryColor);
      const accentHSL = hexToHSL(accentColor);
      
      // Override Tailwind's --primary and --accent CSS variables
      root.style.setProperty('--primary', primaryHSL);
      root.style.setProperty('--accent', accentHSL);
      
      // Keep legacy workspace variables for compatibility
      root.style.setProperty('--workspace-primary', primaryColor);
      root.style.setProperty('--workspace-accent', accentColor);
      root.style.setProperty('--workspace-primary-hsl', primaryHSL);
      root.style.setProperty('--workspace-accent-hsl', accentHSL);
    }
  }, [primaryColor, accentColor]);
  
  // Create dynamic CSS variables for org branding
  const themeStyles = {
    '--org-border-radius': `${orgBorderRadius}px`,
  } as React.CSSProperties;

  return (
    <div 
      className="flex h-screen w-screen overflow-hidden bg-background"
      style={themeStyles}
      data-org-branded="true"
    >
      {/* Left sidebar - Global navigation */}
      <Sidebar />

      {/* Main content area */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {currentWorkspaceId && <PresenceIndicator workspaceId={currentWorkspaceId} />}
        {children}
      </main>

      {/* Right AI pane */}
      <AIPane />
    </div>
  );
}
