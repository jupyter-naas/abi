import React from 'react';
import styles from './styles.module.css';
import mirrorImage from '@site/static/img/cards/fm-miror-tile.png';

export default function MirrorSection() {
  return (
    <section className={styles.section}>
      <div className={styles.sectionContainer}>
        <div className={styles.sectionContent}>
          <h2 className={styles.sectionTitle}>
            Your Enterprise in<br />
            the Mirror
          </h2>
          <div className={styles.sectionText}>
            <p>
              BOB reflects your organization's true state, not just its formal structure. 
              Every decision, interaction, and process is mapped, understood, and optimized. 
              See your enterprise as it really operates, not just how it's supposed to.
            </p>
          </div>
        </div>
        <span className={styles.clipPath}>
          <img 
            src={mirrorImage} 
            alt="Modern office building with reflective glass facade and trees" 
            loading="lazy"
            width="992"
            height="1000"
          />
        </span>
      </div>
    </section>
  );
} 