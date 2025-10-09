import React from 'react';
import clsx from 'clsx';
import styles from './styles.module.css';

const Section = ({ 
  children, 
  className = '', 
  title,
  subtitle,
  variant = 'default', // default, vision, risk, technical, etc.
  ...props 
}) => {
  return (
    <section className={clsx('section', styles.section, styles[variant], className)} {...props}>
      <div className="container">
        <div className={styles.sectionContent}>
          {title && <h2 className={styles.sectionTitle}>{title}</h2>}
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          {children}
        </div>
      </div>
    </section>
  );
};

export default Section; 