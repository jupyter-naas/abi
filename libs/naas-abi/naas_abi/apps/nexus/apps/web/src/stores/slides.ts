'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface SlidesProject {
  slug: string;
  title: string;
  branch: string;
  deck_path: string;
  template_id: string;
  updated_at?: string | null;
  commit_sha?: string | null;
}

interface SlidesState {
  selectedSlug: string | null;
  setSelectedSlug: (slug: string | null) => void;
}

export const useSlidesStore = create<SlidesState>()(
  persist(
    (set) => ({
      selectedSlug: null,
      setSelectedSlug: (slug) => set({ selectedSlug: slug }),
    }),
    { name: 'nexus:slides:selected' },
  ),
);
