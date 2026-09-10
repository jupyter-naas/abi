'use client';

import type { ReactNode } from 'react';
import { useRegisterShellTitle } from './shell-title';
import { useRegisterTopNav } from './topnav-content';

interface HeaderProps {
  title?: string;
  subtitle?: string;
  /**
   * App menu (e.g. Slides File / View). Own row under the workspace chrome
   * so it never sits on the centered search field.
   */
  nav?: ReactNode;
  /** Page-level actions, rendered ahead of the global chrome on the right. */
  actions?: ReactNode;
}

/**
 * Declares this page's topnav content. Renders nothing itself — `TopNav`
 * (mounted once by WorkspaceLayout, spanning the width above main content
 * and the AI chat pane) reads the registration and paints the actual bar,
 * so the pane opens below one persistent header instead of beside a
 * per-page-scoped one. Mobile chrome reads the title separately via
 * useShellTitle, since it owns its own top bar.
 */
export function Header({ title, subtitle, nav, actions }: HeaderProps = {}) {
  useRegisterShellTitle(title, subtitle);
  useRegisterTopNav({ title, subtitle, nav, actions });
  return null;
}
