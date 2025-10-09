import React from 'react';
import Link from '@docusaurus/Link';
import Section from '../Section';
import KnowledgeGraph from './KnowledgeGraph';
import styles from './styles.module.css';

export default function CTASection() {
  return (
    <Section 
      variant="cta"
      title="Ready to Transform Your Enterprise?"
    >
      <KnowledgeGraph />
      <div className={styles.ctaContent}>
        <p className={styles.ctaText}>
          Schedule an executive briefing to see how BOB can revolutionize your organization's cognitive capabilities.
        </p>
        <div className={styles.ctaButtons}>
          <Link
            className="button button--primary button--lg"
            to="/schedule"
          >
            Schedule Executive Briefing
          </Link>
        </div>
      </div>
    </Section>
  );
} 