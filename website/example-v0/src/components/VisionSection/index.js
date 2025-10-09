import React from 'react';
import Section from '../Section';
import styles from './styles.module.css';

export default function VisionSection() {
  return (
    <Section 
      variant="vision"
      title="What if AI wasn't just a tool? What if it was a cognitive extension that understood your domain?"
    >
      <div className={styles.visionText}>
        <p>
          Not generic. Not one-size-fits-all.<br/>
          Specialized. Contextual. Intelligent.
        </p>
        <p>
          ABI is that extension.<br/>
          It creates AI that understands your specific domain, workflows, and business logic.
        </p>
        <p>
          It's not just what you ask.<br/>
          It's how you work. What you need. When you need it.
        </p>
      </div>
    </Section>
  );
} 