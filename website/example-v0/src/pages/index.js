import React from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Hero from '../components/Hero';
import VisionSection from '../components/VisionSection';
import RiskSection from '../components/RiskSection';
import ModulesSection from '../components/ModulesSection';
import MirrorSection from '../components/MirrorSection';
import FutureSection from '../components/FutureSection';
import TechnicalSection from '../components/TechnicalSection';
import ComparisonSection from '../components/ComparisonSection';
import CTASection from '../components/CTASection';

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  
  return (
    <Layout
      title={`Home`}
      description="ABI is an enterprise-grade cognitive infrastructure that provides semantic memory and control across your organization."
      wrapperClassName="homepage"
    >
      <Hero />
      <main>
        <VisionSection />
        <RiskSection />
        <ModulesSection />
        <MirrorSection />
        <FutureSection />
        <TechnicalSection />
        <ComparisonSection />
        <CTASection />
      </main>
    </Layout>
  );
}
