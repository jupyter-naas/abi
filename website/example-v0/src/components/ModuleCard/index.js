import React from 'react';
import styles from './styles.module.css';

const ModuleCard = ({ 
  image,
  imageAlt,
  title,
  description,
  linkUrl
}) => {
  return (
    <div className={styles.moduleCard}>
      <div className={styles.moduleImage}>
        <img 
          src={image} 
          alt={imageAlt} 
          loading="lazy"
          onError={(e) => {
            console.error('Image failed to load:', image);
            e.target.style.display = 'none';
          }}
        />
      </div>
      <div className={styles.moduleContent}>
        <h3 className={styles.moduleTitle}>{title}</h3>
        <div className={styles.moduleDescription}>
          {typeof description === 'string' ? (
            <p>{description}</p>
          ) : (
            description
          )}
        </div>
        <a href={linkUrl} className={styles.moduleLink}>
          Read more
          <svg className={styles.arrow} viewBox="0 0 24 24">
            <path d="M16.01 11H4v2h12.01v3L20 12l-3.99-4z" />
          </svg>
        </a>
      </div>
    </div>
  );
};

export default ModuleCard; 