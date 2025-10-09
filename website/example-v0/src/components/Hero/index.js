import React from 'react';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

const Hero = () => {
  const videoRef = React.useRef(null);

  React.useEffect(() => {
    if (videoRef.current) {
      videoRef.current.play().catch(error => {
        console.log("Video autoplay failed:", error);
      });
    }
  }, []);

  return (
    <header className={styles.heroBanner}>
      <div className={styles.heroVideo}>
        <video
          ref={videoRef}
          autoPlay
          loop
          muted
          playsInline
          poster="/img/hero-poster.jpg"
          aria-hidden="true"
        >
          <source src="/videos/fm-hero-video.mp4" type="video/mp4" />
        </video>
      </div>
      <div className={styles.heroContent}>
        <h1 className={styles.heroTitle}>
          <span className={styles.heroTitleMain}>ABI</span>
          <span className={styles.heroTitleSub}>Agentic Brain Infrastructure</span>
        </h1>
        <p className={styles.heroSubtitle}>
          Build your custom AI with domain expertise, specialized workflows, and enterprise-grade capabilities. One codebase, unlimited possibilities.
        </p>
        <div className={styles.heroButtons}>
          <Link 
            className="button button--primary button--lg" 
            to="/builder"
          >
            Start Building Your AI
          </Link>
        </div>
      </div>
    </header>
  );
};

export default Hero; 