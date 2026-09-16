import { create } from 'zustand';

type State = {
  viewMode: 'layers' | 'graph'; setViewMode: (mode: 'layers' | 'graph') => void;
  layerId: string | null; componentId: string | null; expanded: boolean; dependencies: boolean;
  search: string; tab: 'layers' | 'inspector';
  command: { type: 'focus' | 'in' | 'out'; sequence: number };
  move: (type?: 'focus' | 'in' | 'out') => void;
  select: (layer: string, component?: string) => void;
  reset: () => void;
  setComponentId: (id: string | null) => void;
  setSearch: (search: string) => void;
  setTab: (tab: 'layers' | 'inspector') => void;
  toggleExpanded: () => void; toggleDependencies: () => void;
};
export const useInfrastructure = create<State>((set) => ({
  viewMode: 'layers', setViewMode: viewMode => set({ viewMode }),
  layerId: null, componentId: null, expanded: false, dependencies: true, search: '', tab: 'layers',
  command: { type: 'focus', sequence: 0 },
  move: (type = 'focus') => set(s => ({ command: { type, sequence: s.command.sequence + 1 } })),
  select: (layerId, componentId) => set(s => ({ layerId, componentId: componentId ?? null, tab: componentId ? 'inspector' : 'layers', command: { type: 'focus', sequence: s.command.sequence + 1 } })),
  reset: () => set(s => ({ layerId: null, componentId: null, expanded: false, dependencies: true, search: '', tab: 'layers', command: { type: 'focus', sequence: s.command.sequence + 1 } })),
  setComponentId: componentId => set({ componentId, tab: componentId ? 'inspector' : 'layers' }),
  setSearch: search => set({ search }), setTab: tab => set({ tab }),
  toggleExpanded: () => set(s => ({ expanded: !s.expanded, command: { type: 'focus', sequence: s.command.sequence + 1 } })),
  toggleDependencies: () => set(s => ({ dependencies: !s.dependencies })),
}));
