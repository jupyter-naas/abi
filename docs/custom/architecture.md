# BOB Project Architecture

## Overview

The BOB system architecture is designed with scalability, security, and flexibility in mind. It leverages the ABI framework's core components while adding customizations specific to Forvis Mazars' needs. The architecture will evolve through three distinct phases, progressively moving from NaasAI's infrastructure to Forvis Mazars' environment.

## Deployment Phases

### Phase 1: Alpha Phase

The initial deployment will be fully hosted on NaasAI's secure AWS infrastructure:

- **Frontend**: React application deployed on NaasAI's private Kubernetes cluster, with dedicated API connection to NaasAI API Gateway for user authentication and authorization
- **Backend**: Utilizing AWS EC2 instances with Knative for serverless compute, GitHub Actions for CI/CD automation, and S3 for data storage
- **Code Repository**: Hosted on NaasAI's GitHub for version control
- **Authentication**: Managed through NaasAI's identity services

### Phase 2: Beta Phase

A hybrid deployment model:

- **Frontend**: Continue using the Alpha phase frontend + potential integration with GAIA (Forvis Mazars internal AI platform)
- **Backend**: Parallel running of identical backends on both Forvis Mazars' infrastructure and NaasAI's infrastructure
- **Data Storage**: Migration of data from NaasAI's infrastructure to Forvis Mazars' premises
- **Code Repository**: Transition to Forvis Mazars' version control system on GitLab

### Phase 3: General Availability (GA)

Final production architecture, matching the intended deployment model for client projects:

- **Frontend**: Hosted by NaasAI but optionally deployable on customer's infrastructure (subject to license agreement)
- **Backend**: Hosted on customer's infrastructure
- **Data Storage**: All data hosted on customer's infrastructure
- **Maintenance**: NaasAI provides ongoing support and updates
- **Integration**: Deep integration with customer's existing systems and security protocols

## Core Components

At its core, the BOB architecture enables the following components and data flow:

### User Interfaces

- **Chat Interface**: Primary interaction point for users to query the system
- **Search Interface**: For direct knowledge graph exploration
- **Admin Portal**: For configuration and monitoring

### Data Collection Layer

- **Integration Framework**: Connectors to various data sources
- **Data Harvesting Agents**: Automated data collection processes
- **API Gateway**: Secure access point for external services

### Processing Layer

- **Pipeline System**: Transforming raw data into semantic knowledge
- **Semantic Enrichment Engine**: Adding context and relationships to data
- **NLP Processing**: Natural language understanding components

### Knowledge Layer

- **Ontology Store**: Repository of domain ontologies
- **Knowledge Graph**: Consolidated semantic knowledge representation
- **Inference Engine**: Reasoning over the knowledge graph

### Agent Orchestration

- **Workflow Engine**: Defining business processes
- **Agent Manager**: Coordinating specialized AI agents
- **Task Scheduler**: Managing asynchronous operations

### Security Layer

- **Authentication**: User and service identity management
- **Authorization**: Access control to resources
- **Audit Logging**: Comprehensive activity tracking

## Technology Stack

The BOB Project leverages a modern technology stack including:

- **Programming Languages**: Python, TypeScript
- **Knowledge Graph**: RDF/OWL technologies
- **Backend Framework**: FastAPI
- **Frontend Framework**: React
- **Database**: PostgreSQL, Graph database (Neo4j, Virtuoso), and S3 for data storage
- **LLM Integration**: OpenAI, Anthropic, and other providers
- **Container Orchestration**: Kubernetes, Docker
- **CI/CD**: GitHub Actions, GitLab CI (to be done when we move to GitLab)

## Data Flow Architecture

1. **Data Ingestion**:
   - External data is collected through various integrations
   - Documents, APIs, web scraping, and database connections provide raw data

2. **Data Processing**:
   - Raw data is processed through specialized pipelines
   - Named entity recognition, relationship extraction, and semantic enrichment

3. **Knowledge Population**:
   - Processed data is stored in the semantic knowledge graph (/storage/triplestore) as turtle (.ttl) files
   - Ontology-guided structuring ensures proper semantics

4. **Query Processing**:
   - User queries are interpreted and transformed into knowledge graph queries
   - Multiple reasoning strategies combine to generate comprehensive answers

5. **Action Execution**:
   - Agents orchestrate workflows to accomplish user goals
   - Results are formatted and presented through appropriate UI components

## Integration Points

The BOB system includes integrations with:

- **Forvis Mazars Internal Systems**: GAIA (TBD), Napta (TBD), Akuiteo (from CSV exports provided internally)
- **CRM Systems**: Salesforce (TBD)
- **Document Repositories**: SharePoint, Teams
- **Version Control**: GitLab
- **External Data Sources**: News APIs, industry databases, social networks
- **Office Productivity**: Microsoft Office suite for document generation

This architecture ensures that Forvis Mazars can easily adapt ABI to their specific needs while benefiting from continuous improvements to the core platform. 



