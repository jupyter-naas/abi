import React from 'react';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <div className={styles.footerContent}>
          <div className={styles.footerSection}>
            <h2 className={styles.footerTitle}>ABI Platform</h2>
            <p className={styles.footerDescription}>
              An AI-powered cognitive infrastructure that brings enterprise-grade semantic reasoning and autonomous control to your organization's operations and decision-making.
            </p>
          </div>

          <div className={styles.footerSection}>
            <h2 className={styles.footerTitle}>Features</h2>
            <ul className={styles.footerLinks}>
              <li><Link to="/builder">AI Builder</Link></li>
              <li><Link to="/marketplace">Module Marketplace</Link></li>
              <li><Link to="/tester">AI Tester</Link></li>
            </ul>
          </div>

          <div className={styles.footerSection}>
            <h2 className={styles.footerTitle}>Resources</h2>
            <ul className={styles.footerLinks}>
              <li><a href="https://github.com/jupyter-naas/abi" target="_blank" rel="noopener noreferrer">GitHub Repository ↗</a></li>
              <li><Link to="/docs">Documentation</Link></li>
            </ul>
          </div>

          <div className={styles.footerSection}>
            <h2 className={styles.footerTitle}>Community</h2>
            <div className={styles.contactInfo}>
              <p className={styles.contactName}>Open Source Project</p>
              <p className={styles.contactTitle}>Naas AI Community</p>
              <a href="https://github.com/jupyter-naas/abi" className={styles.contactEmail}>
                github.com/jupyter-naas/abi
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.footerLegal}>
        <div className="container">
          <ul className={styles.legalLinks}>
            <li><Link to="https://www.forvismazars.com/group/en/sitemap">Group Site map</Link></li>
            <li><Link to="https://www.forvismazars.com/group/en/legals/data-and-privacy">Data and privacy</Link></li>
            <li><Link to="https://www.forvismazars.com/group/en/legals/disclaimer">Disclaimer</Link></li>
            <li><Link to="https://www.forvismazars.com/group/en/legals/cookies-policy">Cookies</Link></li>
            <li><Link to="https://www.forvismazars.com/group/en/legals/accessibility">Accessibility</Link></li>
            <li><Link to="https://www.forvismazars.com/group/en/legals/whistleblowing-and-complaint-forms">Whistleblowing and complaint forms</Link></li>
          </ul>
          <div className={styles.copyright}>
            Copyright © 2025 Forvis Mazars. All rights reserved.
          </div>
        </div>
      </div>
    </footer>
  );
} 