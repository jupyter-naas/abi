'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Node types
export interface GraphNode {
  id: string;
  label: string;
  type: string; // References ontology entity type
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  color?: string;
  size?: number;
}

// Edge types
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string; // References ontology relationship type
  label?: string;
  properties?: Record<string, unknown>;
  weight?: number;
}

// Named Graph - a collection of nodes and edges with a context
export interface NamedGraph {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  color?: string;
  nodeCount: number;
  edgeCount: number;
  createdAt: Date;
  updatedAt: Date;
}

// View types for exploring the graph
export type GraphViewType = 'overview' | 'entities' | 'table' | 'sparql';

export interface GraphView {
  id: string;
  name: string;
  type: GraphViewType;
  graphId?: string; // Optional - view can span multiple graphs
  query?: string; // For SPARQL views
  filters?: Record<string, unknown>;
  layout?: 'force' | 'hierarchical' | 'circular' | 'grid';
  createdAt: Date;
}

// Saved queries
export interface SavedQuery {
  id: string;
  name: string;
  description?: string;
  query: string;
  language: 'sparql' | 'cypher' | 'natural';
  graphId?: string;
  results?: number;
  lastRun?: Date;
  createdAt: Date;
}

// Graph statistics
export interface GraphStatistics {
  totalNodes: number;
  totalEdges: number;
  nodesByType: Record<string, number>;
  edgesByType: Record<string, number>;
  avgDegree: number;
  density: number;
  connectedComponents: number;
}

interface KnowledgeGraphState {
  // Named graphs
  graphs: NamedGraph[];
  selectedGraphId: string | null;
  visibleGraphIds: string[]; // Graphs currently visible in the view
  
  // Nodes and edges for current graph
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  
  // Views
  views: GraphView[];
  activeViewType: GraphViewType;
  
  // Queries
  queries: SavedQuery[];
  currentQuery: string;
  queryResults: GraphNode[];
  
  // UI State
  loading: boolean;
  error: string | null;
  zoomLevel: number;
  
  // Actions - Graphs
  createGraph: (name: string, description?: string) => NamedGraph;
  deleteGraph: (id: string) => void;
  selectGraph: (id: string | null) => void;
  updateGraph: (id: string, updates: Partial<NamedGraph>) => void;
  toggleGraphVisibility: (id: string) => void;
  setVisibleGraphs: (ids: string[]) => void;
  
  // Actions - Nodes
  addNode: (node: Omit<GraphNode, 'id'>) => GraphNode;
  updateNode: (id: string, updates: Partial<GraphNode>) => void;
  deleteNode: (id: string) => void;
  selectNode: (id: string | null) => void;
  
  // Actions - Edges
  addEdge: (edge: Omit<GraphEdge, 'id'>) => GraphEdge;
  updateEdge: (id: string, updates: Partial<GraphEdge>) => void;
  deleteEdge: (id: string) => void;
  selectEdge: (id: string | null) => void;
  
  // Actions - Views
  createView: (name: string, type: GraphViewType) => GraphView;
  deleteView: (id: string) => void;
  setActiveViewType: (type: GraphViewType) => void;
  
  // Actions - Queries
  saveQuery: (name: string, query: string, language: SavedQuery['language']) => SavedQuery;
  deleteQuery: (id: string) => void;
  runQuery: (query: string) => Promise<GraphNode[]>;
  setCurrentQuery: (query: string) => void;
  
  // Actions - UI
  setZoomLevel: (level: number) => void;
  
  // Computed
  getStatistics: () => GraphStatistics;
  
  // Demo data
  loadAviationDemo: () => void;
  clearCurrentGraph: () => void;
}

export const useKnowledgeGraphStore = create<KnowledgeGraphState>()(
  persist(
    (set, get) => ({
      graphs: [],
      selectedGraphId: null,
      visibleGraphIds: [],
      nodes: [],
      edges: [],
      selectedNodeId: null,
      selectedEdgeId: null,
      views: [],
      activeViewType: 'overview',
      queries: [],
      currentQuery: '',
      queryResults: [],
      loading: false,
      error: null,
      zoomLevel: 1,

      // Graph actions
      createGraph: (name, description) => {
        const newGraph: NamedGraph = {
          id: `graph-${Date.now()}`,
          name,
          description,
          nodeCount: 0,
          edgeCount: 0,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({ 
          graphs: [...state.graphs, newGraph],
          selectedGraphId: newGraph.id,
        }));
        return newGraph;
      },

      deleteGraph: (id) => {
        set((state) => ({
          graphs: state.graphs.filter((g) => g.id !== id),
          selectedGraphId: state.selectedGraphId === id ? null : state.selectedGraphId,
          // Also clear nodes/edges if this was the selected graph
          nodes: state.selectedGraphId === id ? [] : state.nodes,
          edges: state.selectedGraphId === id ? [] : state.edges,
        }));
      },

      selectGraph: (id) => {
        set({ selectedGraphId: id });
        // TODO: Load nodes/edges for this graph from backend
      },

      updateGraph: (id, updates) => {
        set((state) => ({
          graphs: state.graphs.map((g) =>
            g.id === id ? { ...g, ...updates, updatedAt: new Date() } : g
          ),
        }));
      },

      toggleGraphVisibility: (id) => {
        set((state) => {
          const isVisible = state.visibleGraphIds.includes(id);
          return {
            visibleGraphIds: isVisible
              ? state.visibleGraphIds.filter((gid) => gid !== id)
              : [...state.visibleGraphIds, id],
          };
        });
      },

      setVisibleGraphs: (ids) => {
        set({ visibleGraphIds: ids });
      },

      // Node actions
      addNode: (nodeData) => {
        const node: GraphNode = {
          id: `node-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          ...nodeData,
        };
        set((state) => {
          const newNodes = [...state.nodes, node];
          // Update graph node count
          if (state.selectedGraphId) {
            const graphs = state.graphs.map((g) =>
              g.id === state.selectedGraphId
                ? { ...g, nodeCount: newNodes.length, updatedAt: new Date() }
                : g
            );
            return { nodes: newNodes, graphs };
          }
          return { nodes: newNodes };
        });
        return node;
      },

      updateNode: (id, updates) => {
        set((state) => ({
          nodes: state.nodes.map((n) => (n.id === id ? { ...n, ...updates } : n)),
        }));
      },

      deleteNode: (id) => {
        set((state) => {
          const newNodes = state.nodes.filter((n) => n.id !== id);
          const newEdges = state.edges.filter((e) => e.source !== id && e.target !== id);
          // Update graph counts
          if (state.selectedGraphId) {
            const graphs = state.graphs.map((g) =>
              g.id === state.selectedGraphId
                ? { ...g, nodeCount: newNodes.length, edgeCount: newEdges.length, updatedAt: new Date() }
                : g
            );
            return { 
              nodes: newNodes, 
              edges: newEdges, 
              graphs,
              selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
            };
          }
          return { nodes: newNodes, edges: newEdges };
        });
      },

      selectNode: (id) => set({ selectedNodeId: id, selectedEdgeId: null }),

      // Edge actions
      addEdge: (edgeData) => {
        const edge: GraphEdge = {
          id: `edge-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          ...edgeData,
        };
        set((state) => {
          const newEdges = [...state.edges, edge];
          if (state.selectedGraphId) {
            const graphs = state.graphs.map((g) =>
              g.id === state.selectedGraphId
                ? { ...g, edgeCount: newEdges.length, updatedAt: new Date() }
                : g
            );
            return { edges: newEdges, graphs };
          }
          return { edges: newEdges };
        });
        return edge;
      },

      updateEdge: (id, updates) => {
        set((state) => ({
          edges: state.edges.map((e) => (e.id === id ? { ...e, ...updates } : e)),
        }));
      },

      deleteEdge: (id) => {
        set((state) => {
          const newEdges = state.edges.filter((e) => e.id !== id);
          if (state.selectedGraphId) {
            const graphs = state.graphs.map((g) =>
              g.id === state.selectedGraphId
                ? { ...g, edgeCount: newEdges.length, updatedAt: new Date() }
                : g
            );
            return { 
              edges: newEdges, 
              graphs,
              selectedEdgeId: state.selectedEdgeId === id ? null : state.selectedEdgeId,
            };
          }
          return { edges: newEdges };
        });
      },

      selectEdge: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),

      // View actions
      createView: (name, type) => {
        const view: GraphView = {
          id: `view-${Date.now()}`,
          name,
          type,
          graphId: get().selectedGraphId || undefined,
          createdAt: new Date(),
        };
        set((state) => ({ views: [...state.views, view] }));
        return view;
      },

      deleteView: (id) => {
        set((state) => ({ views: state.views.filter((v) => v.id !== id) }));
      },

      setActiveViewType: (type) => set({ activeViewType: type }),

      // Query actions
      saveQuery: (name, query, language) => {
        const savedQuery: SavedQuery = {
          id: `query-${Date.now()}`,
          name,
          query,
          language,
          graphId: get().selectedGraphId || undefined,
          createdAt: new Date(),
        };
        set((state) => ({ queries: [...state.queries, savedQuery] }));
        return savedQuery;
      },

      deleteQuery: (id) => {
        set((state) => ({ queries: state.queries.filter((q) => q.id !== id) }));
      },

      runQuery: async (query) => {
        set({ loading: true, currentQuery: query });
        // TODO: Implement actual query execution
        // For now, return filtered nodes based on simple pattern matching
        const { nodes } = get();
        const results = nodes.filter((n) =>
          n.label.toLowerCase().includes(query.toLowerCase()) ||
          n.type.toLowerCase().includes(query.toLowerCase())
        );
        set({ queryResults: results, loading: false });
        return results;
      },

      setCurrentQuery: (query) => set({ currentQuery: query }),

      // UI actions
      setZoomLevel: (level) => set({ zoomLevel: Math.max(0.1, Math.min(3, level)) }),

      // Computed statistics
      getStatistics: () => {
        const { nodes, edges } = get();
        
        const nodesByType: Record<string, number> = {};
        nodes.forEach((n) => {
          nodesByType[n.type] = (nodesByType[n.type] || 0) + 1;
        });

        const edgesByType: Record<string, number> = {};
        edges.forEach((e) => {
          edgesByType[e.type] = (edgesByType[e.type] || 0) + 1;
        });

        const totalNodes = nodes.length;
        const totalEdges = edges.length;
        const avgDegree = totalNodes > 0 ? (2 * totalEdges) / totalNodes : 0;
        const maxPossibleEdges = (totalNodes * (totalNodes - 1)) / 2;
        const density = maxPossibleEdges > 0 ? totalEdges / maxPossibleEdges : 0;

        return {
          totalNodes,
          totalEdges,
          nodesByType,
          edgesByType,
          avgDegree,
          density,
          connectedComponents: 1, // TODO: Implement proper algorithm
        };
      },

      // Clear current graph data
      clearCurrentGraph: () => {
        set({ nodes: [], edges: [], selectedNodeId: null, selectedEdgeId: null });
        const { selectedGraphId, graphs } = get();
        if (selectedGraphId) {
          set({
            graphs: graphs.map((g) =>
              g.id === selectedGraphId
                ? { ...g, nodeCount: 0, edgeCount: 0, updatedAt: new Date() }
                : g
            ),
          });
        }
      },

      // (Deprecated) Aviation Demo - keep callable but no-op to avoid legacy graphs
      loadAviationDemo: () => {
        console.warn('loadAviationDemo is deprecated and disabled. Use workspace Person/Organization graphs.');
        return;
        // First create or select the Aviation graph
        let { graphs, selectedGraphId } = get();
        let aviationGraph = graphs.find((g) => g.name === 'Aviation Demo');
        
        if (!aviationGraph) {
          aviationGraph = get().createGraph(
            'Aviation Demo',
            'A demo scenario grounded in BFO 7 Buckets showing a flight from SFO to JFK'
          );
        } else {
          get().selectGraph(aviationGraph!.id);
        }

        // Clear existing data
        get().clearCurrentGraph();

        // ============================================
        // AVIATION DEMO DATA - GROUNDED IN BFO 7 BUCKETS
        // ============================================

        const demoNodes: Omit<GraphNode, 'id'>[] = [
          // WHO - Material Entities (BFO_0000040)
          { label: 'Boeing 737-800', type: 'Material Entity', properties: { registration: 'N12345', manufacturer: 'Boeing', model: '737-800', capacity: 189 }, x: 0, y: 0 },
          { label: 'Captain Sarah Chen', type: 'Material Entity', properties: { role: 'Captain', airline: 'United Airlines', license: 'ATP-123456', flightHours: 15000 }, x: -150, y: -100 },
          { label: 'First Officer James Park', type: 'Material Entity', properties: { role: 'First Officer', airline: 'United Airlines', license: 'ATP-789012' }, x: -150, y: 100 },
          { label: 'United Airlines', type: 'Material Entity', properties: { type: 'Airline', iataCode: 'UA', icaoCode: 'UAL' }, x: -300, y: 0 },
          { label: 'Passenger John Doe', type: 'Material Entity', properties: { seat: '12A', class: 'Economy', frequentFlyer: 'Gold' }, x: 100, y: -150 },
          { label: 'Flight Crew', type: 'Material Entity', properties: { size: 5, positions: ['FA1', 'FA2', 'FA3', 'FA4', 'FA5'] }, x: 100, y: 150 },
          
          // WHAT - Processes (BFO_0000015)
          { label: 'Flight UA123', type: 'Process', properties: { flightNumber: 'UA123', status: 'Completed', distance: '2586 nm' }, x: 200, y: 0 },
          { label: 'Boarding Process', type: 'Process', properties: { duration: '45 min', method: 'Zone boarding' }, x: 300, y: -120 },
          { label: 'Takeoff', type: 'Process', properties: { runway: '28R', v1: '148 kt', vr: '156 kt', v2: '163 kt' }, x: 400, y: -60 },
          { label: 'Cruise', type: 'Process', properties: { altitude: 'FL350', speed: '485 kt', duration: '4h 30m' }, x: 500, y: 0 },
          { label: 'Landing', type: 'Process', properties: { runway: '31R', autoland: false, category: 'CAT I' }, x: 400, y: 60 },
          { label: 'Pre-flight Check', type: 'Process', properties: { items: 42, duration: '30 min' }, x: 200, y: -180 },
          
          // WHEN - Temporal Regions (BFO_0000008)
          { label: 'Departure Time', type: 'Temporal Region', properties: { datetime: '2026-02-03T08:00:00-08:00', timezone: 'PST' }, x: 250, y: -250 },
          { label: 'Arrival Time', type: 'Temporal Region', properties: { datetime: '2026-02-03T16:30:00-05:00', timezone: 'EST' }, x: 550, y: -250 },
          { label: 'Block Time', type: 'Temporal Region', properties: { duration: '5h 30m', type: 'interval' }, x: 400, y: -250 },
          
          // WHERE - Sites (BFO_0000029)
          { label: 'San Francisco Intl (SFO)', type: 'Site', properties: { iataCode: 'SFO', icaoCode: 'KSFO', elevation: '13 ft', city: 'San Francisco' }, x: -200, y: -250 },
          { label: 'John F Kennedy Intl (JFK)', type: 'Site', properties: { iataCode: 'JFK', icaoCode: 'KJFK', elevation: '13 ft', city: 'New York' }, x: 600, y: -250 },
          { label: 'Gate A14 (SFO)', type: 'Site', properties: { terminal: 'A', type: 'Gate' }, x: -100, y: -200 },
          { label: 'Runway 28R (SFO)', type: 'Site', properties: { length: '11870 ft', surface: 'Asphalt', ils: true }, x: -50, y: -150 },
          { label: 'US Airspace', type: 'Site', properties: { type: 'Controlled Airspace', class: 'A' }, x: 400, y: -180 },
          
          // HOW IT IS - Qualities (BFO_0000019)
          { label: 'Cruise Altitude', type: 'Quality', properties: { value: 35000, unit: 'feet', flightLevel: 'FL350' }, x: 550, y: 100 },
          { label: 'Ground Speed', type: 'Quality', properties: { value: 485, unit: 'knots' }, x: 600, y: 50 },
          { label: 'Fuel State', type: 'Quality', properties: { onboard: 45000, unit: 'lbs', burnRate: '5500 lbs/hr' }, x: 650, y: 100 },
          { label: 'Weather Conditions', type: 'Quality', properties: { visibility: '10 SM', ceiling: 'CLR', wind: '270/15' }, x: 500, y: 150 },
          
          // WHY - Roles (BFO_0000023)
          { label: 'Pilot in Command Role', type: 'Role', properties: { authority: 'Final', responsibility: 'Safety of flight' }, x: -250, y: -150 },
          { label: 'Passenger Role', type: 'Role', properties: { rights: ['Transport', 'Safety', 'Information'], duties: ['Follow crew instructions'] }, x: 150, y: -200 },
          { label: 'Air Traffic Control Role', type: 'Role', properties: { facility: 'Oakland Center', frequency: '127.85' }, x: 350, y: 200 },
          
          // WHY - Dispositions (BFO_0000016)
          { label: 'Flight Capability', type: 'Disposition', properties: { maxAltitude: 41000, maxSpeed: 544, range: 3115 }, x: -100, y: 100 },
          { label: 'Emergency Landing Capability', type: 'Disposition', properties: { type: 'ETOPS-180', diversion: 'Any suitable airport' }, x: 0, y: 150 },
          
          // HOW WE KNOW - GDC (BFO_0000031)
          { label: 'Flight Plan UA123', type: 'GDC', properties: { format: 'ICAO', route: 'SFO KAYEX Q92 MVA J80 JFK', alternates: ['EWR', 'LGA'] }, x: -300, y: 150 },
          { label: 'Boarding Pass #BP12345', type: 'GDC', properties: { passenger: 'John Doe', seat: '12A', boardingGroup: 2 }, x: 50, y: -250 },
          { label: 'Weather Report METAR', type: 'GDC', properties: { station: 'KSFO', type: 'METAR', raw: 'KSFO 031200Z 27015KT 10SM CLR 18/08 A3012' }, x: -200, y: 200 },
          { label: 'Load Manifest', type: 'GDC', properties: { passengers: 156, bags: 245, cargo: '2500 lbs', zfw: '115000 lbs' }, x: -100, y: 250 },
          { label: 'ATC Clearance', type: 'GDC', properties: { squawk: '4523', initialAltitude: 'FL350', route: 'As filed' }, x: 250, y: 250 },
        ];

        // Add nodes
        const nodeIdMap: Record<string, string> = {};
        demoNodes.forEach((nodeData) => {
          const node = get().addNode(nodeData);
          nodeIdMap[nodeData.label] = node.id;
        });

        // Define edges based on BFO relationships
        const demoEdges: Array<{ source: string; target: string; type: string; label?: string }> = [
          // Material Entity relationships
          { source: 'Captain Sarah Chen', target: 'United Airlines', type: 'member of' },
          { source: 'First Officer James Park', target: 'United Airlines', type: 'member of' },
          { source: 'Boeing 737-800', target: 'United Airlines', type: 'owned by' },
          { source: 'Flight Crew', target: 'Boeing 737-800', type: 'located in' },
          
          // Process relationships (participates in)
          { source: 'Boeing 737-800', target: 'Flight UA123', type: 'participates in' },
          { source: 'Captain Sarah Chen', target: 'Flight UA123', type: 'participates in' },
          { source: 'First Officer James Park', target: 'Flight UA123', type: 'participates in' },
          { source: 'Passenger John Doe', target: 'Boarding Process', type: 'participates in' },
          { source: 'Flight Crew', target: 'Flight UA123', type: 'participates in' },
          
          // Process sequence (precedes)
          { source: 'Pre-flight Check', target: 'Boarding Process', type: 'precedes' },
          { source: 'Boarding Process', target: 'Takeoff', type: 'precedes' },
          { source: 'Takeoff', target: 'Cruise', type: 'precedes' },
          { source: 'Cruise', target: 'Landing', type: 'precedes' },
          
          // Process occurs in Site
          { source: 'Boarding Process', target: 'Gate A14 (SFO)', type: 'occurs in' },
          { source: 'Takeoff', target: 'Runway 28R (SFO)', type: 'occurs in' },
          { source: 'Cruise', target: 'US Airspace', type: 'occurs in' },
          { source: 'Flight UA123', target: 'San Francisco Intl (SFO)', type: 'departs from' },
          { source: 'Flight UA123', target: 'John F Kennedy Intl (JFK)', type: 'arrives at' },
          
          // Temporal relations
          { source: 'Flight UA123', target: 'Block Time', type: 'occupies temporal region' },
          { source: 'Takeoff', target: 'Departure Time', type: 'occurs at' },
          { source: 'Landing', target: 'Arrival Time', type: 'occurs at' },
          
          // Quality inheres in
          { source: 'Cruise Altitude', target: 'Boeing 737-800', type: 'inheres in' },
          { source: 'Ground Speed', target: 'Boeing 737-800', type: 'inheres in' },
          { source: 'Fuel State', target: 'Boeing 737-800', type: 'inheres in' },
          { source: 'Weather Conditions', target: 'San Francisco Intl (SFO)', type: 'inheres in' },
          
          // Role relationships
          { source: 'Captain Sarah Chen', target: 'Pilot in Command Role', type: 'bearer of' },
          { source: 'Passenger John Doe', target: 'Passenger Role', type: 'bearer of' },
          { source: 'Flight UA123', target: 'Pilot in Command Role', type: 'realizes' },
          { source: 'Flight UA123', target: 'Air Traffic Control Role', type: 'realizes' },
          
          // Disposition relationships
          { source: 'Boeing 737-800', target: 'Flight Capability', type: 'bearer of' },
          { source: 'Boeing 737-800', target: 'Emergency Landing Capability', type: 'bearer of' },
          { source: 'Flight UA123', target: 'Flight Capability', type: 'realizes' },
          
          // GDC relationships
          { source: 'Flight Plan UA123', target: 'Boeing 737-800', type: 'generically depends on' },
          { source: 'Boarding Pass #BP12345', target: 'Passenger John Doe', type: 'is carrier of' },
          { source: 'Flight UA123', target: 'Flight Plan UA123', type: 'concretizes' },
          { source: 'Weather Report METAR', target: 'San Francisco Intl (SFO)', type: 'generically depends on' },
          { source: 'Load Manifest', target: 'Boeing 737-800', type: 'generically depends on' },
          { source: 'ATC Clearance', target: 'Flight UA123', type: 'authorizes' },
          
          // Site containment
          { source: 'Gate A14 (SFO)', target: 'San Francisco Intl (SFO)', type: 'part of' },
          { source: 'Runway 28R (SFO)', target: 'San Francisco Intl (SFO)', type: 'part of' },
        ];

        // Add edges
        demoEdges.forEach((edgeData) => {
          const sourceId = nodeIdMap[edgeData.source];
          const targetId = nodeIdMap[edgeData.target];
          if (sourceId && targetId) {
            get().addEdge({
              source: sourceId,
              target: targetId,
              type: edgeData.type,
              label: edgeData.label || edgeData.type,
            });
          }
        });
      },
    }),
    {
      name: 'nexus-knowledge-graph',
      partialize: (state) => ({
        graphs: state.graphs,
        views: state.views,
        queries: state.queries,
        selectedGraphId: state.selectedGraphId,
      }),
    }
  )
);
