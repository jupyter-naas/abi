import React from 'react';

const FeatureCard = ({ icon: Icon, title, description, className = '', ...props }) => {
  const cardClass = `feature-card ${className}`.trim();
  
  return (
    <div 
      className={cardClass}
      {...props}
    >
      {Icon && (
        <div className="feature-icon">
          <Icon />
        </div>
      )}
      <div className="feature-content">
        {title && <h3>{title}</h3>}
        {description && <p>{description}</p>}
      </div>
    </div>
  );
};

export default FeatureCard; 