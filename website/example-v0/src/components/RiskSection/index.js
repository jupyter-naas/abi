import React from 'react';
import Section from '../Section';
import styles from './styles.module.css';

export default function RiskSection() {
  return (
    <Section
      variant="risk"
      title="The Risk Has Shifted"
    >
      <div className={styles.riskText}>
        <p>
          Decisions are no longer only made by people.<br/>
          They're made by autonomous agents, integrated APIs, and disconnected applications operating faster than any org chart.
        </p>
        <p>
          The danger isn't bad data.<br/>
          The danger is action without explanation.
        </p>
        <p>
          BOB restores clarity. It introduces an AI cognitive infrastructure that mirrors your organization's true state.
        </p>
      </div>
    </Section>
  );
} 