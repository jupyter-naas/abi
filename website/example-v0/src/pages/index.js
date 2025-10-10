import React from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  
  return (
    <Layout
      title="Home"
      description="ABI - Agentic Brain Infrastructure for building custom AI systems"
    >
      <header className="hero hero--primary">
        <div className="container">
          <h1 className="hero__title">ABI</h1>
          <p className="hero__subtitle">Agentic Brain Infrastructure</p>
          <p className="hero__subtitle">
            Build custom AI systems with domain expertise, specialized workflows, and enterprise-grade capabilities.
          </p>
          <div className="hero__buttons">
            <Link
              className="button button--secondary button--lg"
              to="/docs/intro">
              Get Started
            </Link>
            <Link
              className="button button--outline button--lg margin-left--md"
              to="/chat">
              Try Chat
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="padding-vert--xl">
          <div className="container">
            <div className="row">
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>🧠 Modular Architecture</h3>
                  <p>
                    Compose AI systems from specialized modules including domain experts, 
                    AI models, and workflow integrations.
                  </p>
                </div>
              </div>
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>🔗 Semantic Knowledge</h3>
                  <p>
                    Built on ontology-driven architecture with knowledge graphs 
                    for intelligent reasoning and context understanding.
                  </p>
                </div>
              </div>
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>⚡ Multi-Model Support</h3>
                  <p>
                    Access multiple AI models (GPT-4, Claude, Gemini, Llama) 
                    with intelligent routing and orchestration.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}