import React from 'react';
import Section from '../Section';
import TechnicalCard from '../TechnicalCard';
import styles from './styles.module.css';

const features = [
  {
    title: 'Enterprise Integration',
    description: 'Seamlessly connects with your existing infrastructure, databases, and APIs through our robust integration layer.',
    icon: '🔄'
  },
  {
    title: 'Semantic Processing',
    description: 'Advanced NLP and knowledge graph capabilities enable deep understanding of context, relationships, and business logic.',
    icon: '🧠'
  },
  {
    title: 'Real-time Analysis',
    description: 'Process and analyze data streams in real-time with sub-second latency for immediate actionable insights.',
    icon: '⚡'
  },
  {
    title: 'Enterprise Security',
    description: 'Built with bank-grade security, encryption, and compliance features including SOC 2, GDPR, and ISO 27001.',
    icon: '🔒'
  },
  {
    title: 'Scalable Architecture',
    description: 'Cloud-native design scales effortlessly from proof-of-concept to global enterprise deployment.',
    icon: '📈'
  },
  {
    title: 'Developer Experience',
    description: 'Comprehensive APIs, SDKs, and documentation make integration and customization straightforward.',
    icon: '👨‍💻'
  }
];

export default function TechnicalSection() {
  return (
    <Section 
      variant="technical"
      title="Technical Excellence"
      subtitle="Enterprise-grade infrastructure built for scale, security, and seamless integration"
    >
      <div className={styles.technicalGrid}>
        {features.map((feature, index) => (
          <TechnicalCard key={index} {...feature} />
        ))}
      </div>
    </Section>
  );
} 