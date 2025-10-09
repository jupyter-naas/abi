import React from 'react';
import styles from './styles.module.css';

export default function TechnicalCard({ title, description, icon }) {
  return (
    <div className={styles.technicalCard}>
      <span className={styles.icon}>{icon}</span>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
    </div>
  );
} 