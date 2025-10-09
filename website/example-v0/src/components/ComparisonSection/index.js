import React from 'react';
import Section from '../Section';
import ComparisonTable from '../ComparisonTable';
import styles from './styles.module.css';

export default function ComparisonSection() {
  return (
    <Section 
      variant="comparison"
      title="Why BOB?"
      subtitle="Compare BOB with traditional enterprise solutions"
    >
      <div className={styles.comparisonContent}>
        <ComparisonTable />
      </div>
    </Section>
  );
} 