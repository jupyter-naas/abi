import React from 'react';
import styles from './styles.module.css';

const features = [
  {
    feature: 'Semantic Understanding',
    bob: 'Deep contextual understanding of enterprise data',
    traditional: 'Basic keyword and metadata search'
  },
  {
    feature: 'Knowledge Integration',
    bob: 'Unified knowledge graph across all systems',
    traditional: 'Siloed data in separate systems'
  },
  {
    feature: 'AI Governance',
    bob: 'Built-in control and auditability',
    traditional: 'Limited oversight of AI systems'
  },
  {
    feature: 'Real-time Processing',
    bob: 'Continuous analysis and updates',
    traditional: 'Periodic batch processing'
  },
  {
    feature: 'Scalability',
    bob: 'Enterprise-grade, cloud-native architecture',
    traditional: 'Limited by traditional infrastructure'
  }
];

export default function ComparisonTable() {
  return (
    <div className={styles.tableWrapper}>
      <table className={styles.comparisonTable}>
        <thead>
          <tr>
            <th>Feature</th>
            <th>BOB</th>
            <th>Traditional Solutions</th>
          </tr>
        </thead>
        <tbody>
          {features.map((item, index) => (
            <tr key={index}>
              <td>{item.feature}</td>
              <td>{item.bob}</td>
              <td>{item.traditional}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
} 