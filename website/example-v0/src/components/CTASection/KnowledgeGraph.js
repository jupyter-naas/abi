import React, { useEffect, useRef } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import styles from './styles.module.css';

const ENTERPRISE_NODES = [
  { id: 'people', label: '👥 People', group: 1, title: 'People in your organization' },
  { id: 'skills', label: '🎯 Skills', group: 1, title: 'Individual and team capabilities' },
  { id: 'resources', label: '🔧 Resources', group: 2, title: 'Available resources' },
  { id: 'assets', label: '💎 Assets', group: 2, title: 'Company assets' },
  { id: 'projects', label: '📊 Projects', group: 3, title: 'Ongoing projects' },
  { id: 'tasks', label: '✓ Tasks', group: 3, title: 'Project tasks' },
  { id: 'organization', label: '🏢 Organization', group: 4, title: 'Organizational structure' },
  { id: 'policies', label: '📜 Policies', group: 4, title: 'Company policies' },
  { id: 'events', label: '📅 Events', group: 5, title: 'Important events' },
  { id: 'conversations', label: '💬 Conversations', group: 5, title: 'Team communications' },
  { id: 'contracts', label: '📄 Contracts', group: 6, title: 'Legal agreements' },
  { id: 'transactions', label: '💱 Transactions', group: 6, title: 'Business transactions' }
];

const CONNECTIONS = [
  { from: 'people', to: 'skills' },
  { from: 'people', to: 'projects' },
  { from: 'people', to: 'organization' },
  { from: 'people', to: 'conversations' },
  { from: 'people', to: 'events' },
  { from: 'organization', to: 'policies' },
  { from: 'organization', to: 'resources' },
  { from: 'organization', to: 'contracts' },
  { from: 'organization', to: 'projects' },
  { from: 'projects', to: 'tasks' },
  { from: 'projects', to: 'resources' },
  { from: 'projects', to: 'assets' },
  { from: 'projects', to: 'conversations' },
  { from: 'resources', to: 'assets' },
  { from: 'resources', to: 'tasks' },
  { from: 'conversations', to: 'events' },
  { from: 'conversations', to: 'tasks' },
  { from: 'policies', to: 'contracts' },
  { from: 'contracts', to: 'transactions' },
  { from: 'skills', to: 'tasks' },
  { from: 'skills', to: 'projects' }
];

const GROUP_COLORS = {
  1: 'rgba(42, 140, 224, 0.6)',
  2: 'rgba(52, 211, 153, 0.6)',
  3: 'rgba(245, 158, 11, 0.6)',
  4: 'rgba(139, 92, 246, 0.6)',
  5: 'rgba(236, 72, 153, 0.6)',
  6: 'rgba(99, 102, 241, 0.6)'
};

export default function KnowledgeGraph() {
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create the datasets
    const nodes = new DataSet(ENTERPRISE_NODES.map(node => ({
      ...node,
      color: {
        background: GROUP_COLORS[node.group],
        border: GROUP_COLORS[node.group],
        highlight: { 
          background: GROUP_COLORS[node.group].replace('0.6)', '0.9)'),
          border: GROUP_COLORS[node.group].replace('0.6)', '1)')
        }
      },
      font: { 
        color: '#666666',
        size: 14,
        strokeWidth: 0,
      },
      size: 30,
      borderWidth: 1,
      shadow: {
        enabled: true,
        color: 'rgba(0,0,0,0.2)',
        size: 5,
        x: 0,
        y: 2
      }
    })));

    const edges = new DataSet(CONNECTIONS.map(conn => ({
      ...conn,
      color: { 
        color: 'rgba(0, 0, 0, 0.2)',
        opacity: 0.5,
        highlight: 'rgba(0, 0, 0, 0.5)'
      },
      width: 2,
      smooth: {
        type: 'curvedCW',
        roundness: 0.2
      },
      shadow: {
        enabled: false
      }
    })));

    // Configuration for the network
    const options = {
      nodes: {
        shape: 'dot',
        scaling: {
          min: 20,
          max: 30
        },
        margin: 12,
      },
      edges: {
        width: 2,
        selectionWidth: 3,
        smooth: {
          type: 'continuous'
        }
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -1000,
          centralGravity: 0.2,
          springLength: 150,
          springConstant: 0.04,
          damping: 0.09
        },
        stabilization: {
          enabled: true,
          iterations: 1000,
          updateInterval: 100
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: false,
        dragView: false
      }
    };

    // Create the network
    networkRef.current = new Network(
      containerRef.current,
      { nodes, edges },
      options
    );

    // Add event listeners
    networkRef.current.on('hoverNode', (params) => {
      containerRef.current.style.cursor = 'pointer';
    });
    
    networkRef.current.on('blurNode', (params) => {
      containerRef.current.style.cursor = 'default';
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, []);

  return (
    <>
      <div className={styles.graphOverlay} />
      <div ref={containerRef} className={styles.graphBackground} />
    </>
  );
} 