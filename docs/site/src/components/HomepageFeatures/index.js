import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
 {
 title: 'AI Networks as a Service',
 description: (
 <>
 Build intelligent AI assistants that work together as a unified network.
 Create powerful organizational AI systems that learn and scale.
 </>
 ),
 },
 {
 title: 'Ontology-Driven Intelligence',
 description: (
 <>
 Structure your data with ontologies that enable AI models to understand
 relationships, context, and meaning across your entire organization.
 </>
 ),
 },
 {
 title: 'Workflow Automation',
 description: (
 <>
 Automate business processes with AI-powered workflows that integrate
 data, analytics, and external systems for maximum efficiency.
 </>
 ),
 },
];

function Feature({title, description}) {
 return (
 <div className={clsx('col col--4')}>
 <div className="text--center padding-horiz--md">
 <Heading as="h3">{title}</Heading>
 <p>{description}</p>
 </div>
 </div>
 );
}

export default function HomepageFeatures() {
 return (
 <section className={styles.features}>
 <div className="container">
 <div className="row">
 {FeatureList.map((props, idx) => (
 <Feature key={idx} {...props} />
 ))}
 </div>
 </div>
 </section>
 );
}
