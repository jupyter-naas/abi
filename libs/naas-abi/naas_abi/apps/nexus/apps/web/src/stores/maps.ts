'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MapsDatasetCategory } from '@/app/workspace/[workspaceId]/maps/lib/datasets';

export interface MapsState {
  /** Expanded Public / Private / Custom groups in the Maps sidebar. */
  expandedCategories: MapsDatasetCategory[];
  toggleCategory: (category: MapsDatasetCategory) => void;
}

export const useMapsStore = create<MapsState>()(
  persist(
    (set, get) => ({
      // Mirror Search: all three source buckets expanded by default.
      expandedCategories: ['public', 'private', 'custom'],

      toggleCategory: (category) =>
        set({
          expandedCategories: get().expandedCategories.includes(category)
            ? get().expandedCategories.filter((c) => c !== category)
            : [...get().expandedCategories, category],
        }),
    }),
    { name: 'nexus-maps' },
  ),
);
