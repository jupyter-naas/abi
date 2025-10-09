import React from 'react';
import styles from './styles.module.css';

const CapabilityCard = ({ 
  icon,
  text,
  className = '',
  ...props 
}) => {
  return (
    <div className={styles.capabilityCard} {...props}>
      <span className={styles.capabilityIcon}>{icon}</span>
      <p>{text}</p>
    </div>
  );
};

export default CapabilityCard; 