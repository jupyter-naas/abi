'use client';

import { useCallback, useEffect, useState } from 'react';
import { ColumnResizeHandle, useColumnResize } from '@/components/shell/column-resize-handle';

/** Width of the settings nav (Organization and Platform Settings share it). */
export const SETTINGS_NAV_WIDTH_DEFAULT = 224;
export const SETTINGS_NAV_WIDTH_MIN = 180;
export const SETTINGS_NAV_WIDTH_MAX = 480;
const STORAGE_KEY = 'nexus-settings-nav-width';

export function clampSettingsNavWidth(width: number): number {
  if (!Number.isFinite(width)) return SETTINGS_NAV_WIDTH_DEFAULT;
  return Math.max(SETTINGS_NAV_WIDTH_MIN, Math.min(SETTINGS_NAV_WIDTH_MAX, Math.round(width)));
}

function readStoredWidth(): number {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? clampSettingsNavWidth(Number(stored)) : SETTINGS_NAV_WIDTH_DEFAULT;
  } catch {
    return SETTINGS_NAV_WIDTH_DEFAULT;
  }
}

/** Nav width, remembered per browser (a viewer convenience, not shared state). */
function useSettingsNavWidth(): [number, (next: number) => void] {
  const [width, setWidthState] = useState(SETTINGS_NAV_WIDTH_DEFAULT);

  useEffect(() => {
    setWidthState(readStoredWidth());
  }, []);

  const setWidth = useCallback((next: number) => {
    const clamped = clampSettingsNavWidth(next);
    setWidthState(clamped);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(clamped));
    } catch {
      // Storage can be blocked; the width then lasts for this page only.
    }
  }, []);

  return [width, setWidth];
}

/**
 * Left nav of the settings shells (Organization Settings, Platform Settings).
 * On desktop it can be resized by dragging its right edge, like the workspace
 * sidebar. In the mobile list it takes the full width and is not resizable.
 */
export function SettingsLayoutNav({
  title,
  resizable = true,
  children,
}: {
  title: string;
  /** False in the mobile list, where the nav fills the screen. */
  resizable?: boolean;
  children: React.ReactNode;
}) {
  const [width, setWidth] = useSettingsNavWidth();
  const { isDragging, handleDragStart } = useColumnResize(width, setWidth);

  return (
    <>
      {isDragging && <div className="fixed inset-0 z-50 cursor-col-resize" />}
      <nav className="settings-layout-nav" style={resizable ? { width } : undefined}>
        <h2 className="settings-layout-nav-title">{title}</h2>
        <div className="settings-layout-nav-divider" />
        {children}
      </nav>
      {resizable && (
        <ColumnResizeHandle
          onMouseDown={handleDragStart}
          label="Drag to resize settings navigation"
          isActive={isDragging}
        />
      )}
    </>
  );
}
