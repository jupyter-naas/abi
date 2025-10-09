import React from 'react';
import Section from '../Section';
import ModuleCard from '../ModuleCard';
import styles from './styles.module.css';

const modules = [
  {
    image: 'img/cards/fm-market-intelligence-tile.jpg',
    imageAlt: 'Market Intelligence',
    title: 'Market Intelligence',
    description: (
      <>
        <p>Continuously scans your environment: clients, competitors, regulators, risks.</p>
        <p>Feeds a live knowledge graph that informs strategy, policy, and positioning.</p>
      </>
    ),
    linkUrl: '/docs/solutions/market-intelligence'
  },
  {
    image: 'img/cards/fm-market-intelligence-tile.jpg',
    imageAlt: 'Capability Mapping',
    title: 'Offer & Capability Mapping',
    description: (
      <>
        <p>Maps every skill, project, method, and service internally.</p>
        <p>Transforms fragmented knowledge into a deployable operating model.</p>
      </>
    ),
    linkUrl: '/docs/solutions/capability-mapping'
  },
  {
    image: 'img/cards/fm-market-intelligence-tile.jpg',
    imageAlt: 'Governance',
    title: 'Human-in-the-Loop Governance',
    description: (
      <>
        <p>Every action human or agentic is governed by explainable logic.</p>
        <p>Auditable. Traceable. Controllable.</p>
      </>
    ),
    linkUrl: '/docs/solutions/governance'
  }
];

export default function ModulesSection() {
  return (
    <Section 
      title="BOB: A Cognitive Infrastructure Starting with 3 Core Modules"
      className={styles.modulesSection}
    >
      <div className={styles.moduleGrid}>
        {modules.map((module, index) => (
          <ModuleCard key={index} {...module} />
        ))}
      </div>
      <p className={styles.moduleFooter}>
        BOB connects these layers in a feedback loop.<br/>
        You no longer react to signals. You reason with them.<br/>
        <span className={styles.moreToCome}>More modules coming soon...</span>
      </p>
    </Section>
  );
} 