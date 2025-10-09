import React from 'react';
import Section from '../Section';
import styles from './styles.module.css';

export default function FutureSection() {
  return (
    <Section 
      variant="future"
      title="The Future is Cognitive"
    >
      <div className={styles.futureContent}>
        <div className={styles.futureGrid}>
          <div className={styles.futureItem}>
            <h3>Autonomous Systems</h3>
            <p>AI agents are making more decisions than humans in many organizations. BOB ensures they remain aligned with your goals.</p>
          </div>
          <div className={styles.futureItem}>
            <h3>Knowledge Integration</h3>
            <p>Break down silos and create a unified knowledge graph that grows smarter with every interaction.</p>
          </div>
          <div className={styles.futureItem}>
            <h3>Cognitive Control</h3>
            <p>Maintain control and visibility over your AI systems while allowing them to operate at machine speed.</p>
          </div>
        </div>
      </div>
    </Section>
  );
} 