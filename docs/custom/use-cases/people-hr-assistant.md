# People HR Assistant

## Overview

The People HR Assistant is an intelligent agent designed to provide comprehensive HR-related information by interfacing with a semantic knowledge base (triple store). It processes natural language queries about employees, their skills, experience, and organizational structure.

### How to use the People HR Assistant 

To use the People HR Assistant, there are two modes available:

Dev: Start with 'make chat-hr-agent' from your terminal
Prod: Use @people-hr-assistant from naas.ai

## Features

### 1. Talent Search
- Search by skills
- Experience level filtering
- Role-based search
- Project experience matching

### 2. Employee Information Retrieval
- Comprehensive profile access
- Career progression tracking
- Skills and certifications
- Project history

### 3. Organizational Insights (TODO)
- Team structure visualization
- Reporting relationships
- Department information
- Resource allocation

## System Architecture

### 1. Core Components

#### 1.1 Query Processing Layer
- **Natural Language Understanding**
  - Converts human queries into structured SPARQL queries
  - Maintains conversation context for follow-up questions
  - Handles query disambiguation

#### 1.2 Data Layer
- **Triple Store Integration**
  - Stores employee data in RDF format
  - Uses SPARQL for querying
  - Maintains data consistency and relationships

#### 1.3 Response Generation
- **Intelligent Response Formatting**
  - Converts raw data into natural language responses
  - Handles data privacy and access control
  - Provides contextual explanations

### 2. Query Categories

#### 2.1 Personal Information
- Basic employee details
- Current position and status
- Work location
- Company affiliation

#### 2.2 Professional Information
- Skills and expertise
- Work history
- Project involvement
- Technical competencies

#### 2.3 Educational Background
- Academic qualifications
- Professional certifications
- Training records

#### 2.4 Organizational Data
- Reporting relationships
- Team structure
- Department information

## Implementation Details

### 1. Data Model

```turtle
# Example RDF
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# Person Class
abi:Person a rdfs:Class .

# Skills Property
abi:ProfessionalSkills a rdfs:Class ;
    rdfs:label "Professional Skills" .

# Relationships
abi:isSkillOf a rdf:Property ;
    rdfs:domain abi:ProfessionalSkills ;
    rdfs:range abi:Person .
```

### 2. Query Processing Flow

1. **Input Processing**
   - Accepts natural language queries about employee skills and capabilities
   - Parses key information from unstructured text
   - Handles variations in phrasing and terminology
   - Example queries:
     - "Who has experience with Python?"
     - "Find developers skilled in cloud computing"
     - "Show me team members with machine learning expertise"

2. **SPARQL Query Generation**
   ```sparql
   SELECT DISTINCT ?person
   WHERE {
       ?skill a abi:ProfessionalSkills ;
             rdfs:label ?label ;
             abi:isSkillOf ?person .
       FILTER(CONTAINS(LCASE(?label), LCASE("${skill_name}")))
   }
   ```

3. **Response Handling**
   - Formats query results into natural language responses
     - Converts raw data into grammatically correct sentences
     - Maintains consistent tone and style
     - Example: "I found 3 team members with Python expertise. John Smith has 5 years of experience and specializes in web development..."
   - Applies privacy filters based on user permissions
     - Masks sensitive information
     - Filters out confidential project details
     - Respects data access levels
     - Example: "Contact HR for detailed information"
   - Handles missing or incomplete data gracefully
     - Provides explanatory messages for gaps
     - Suggests alternative queries when appropriate
     - Maintains response quality despite partial data
     - Example: "Skills information is not available for this employee. You may want to check their LinkedIn profile or contact their manager."
   - Enriches responses with relevant context
     - Includes team/department context
     - Adds skill level indicators
     - References related projects
     - Example: "Alice leads the Data Science team and has expert-level Python skills demonstrated in the Customer Analytics project."


## Usage Examples

### 1. Basic Queries

```plaintext
Q: "Who has experience with Python?"
A: "I found 3 employees with Python experience:
   - John Doe (Senior Developer, 5 years experience)
   - Jane Smith (Technical Lead, 7 years experience)
   - Mike Johnson (Software Engineer, 3 years experience)"
```

### 2. Complex Queries

```plaintext
Q: "Show me team members who have both cloud architecture experience and project management certification"
A: "Found 2 matching profiles:
   - Sarah Williams
     * AWS Solutions Architect (Certified)
     * PMP Certified
     * Leading 3 cloud migration projects
   - James Chen
     * Azure Architecture Specialist
     * PRINCE2 Practitioner
     * Cloud Strategy Lead"
```

## Future Enhancements
- Build automated tests: define ground truth answers and use it to test the accuracy of the assistant and show that SPARQL can bring 99% trust score vs 80% when using LLM to generate the query 
- Build analytics dashboard: user the SPARQL queries to build Dash Plotly dashboard 
  - Indicators: 
    - Total Headcount by Department
      Example: "Engineering: 45, Data Science: 23, Product: 12"
    - Average Years of Experience
      Example: "Overall: 5.3 years, Senior Level: 8.2 years"
    - Skills Coverage Rate
      Example: "Python: 85%, Cloud: 70%, ML: 45%"
    - Resource Utilization Rate
      Example: "Current: 87%, Q1 Target: 85%"
    - Training Budget Utilization
      Example: "$45,000 spent / $60,000 budgeted (75%)"
    - Employee Satisfaction Score
      Example: "4.2/5 (↑0.3 from last quarter)"
  - Charts:
    - Skills Distribution Heatmap
      Example: Matrix showing skills (rows) vs departments (columns) with color intensity indicating proficiency level
    - Experience Level Distribution
      Example: Stacked bars showing Junior/Mid/Senior distribution per department
    - Project Allocation Timeline
      Example: Gantt chart showing which teams/people are allocated to which projects over time
    - Skills Gap Analysis
      Example: Radar chart comparing required skills (target) vs current team capabilities (actual)
- Career path recommendations: "What should I do to become a Ontology Engineer?"
- Integration with HR systems: Napta for skills mapping are captured in Forvis Mazars system and could be added in the ontology
- Custom report generation: use code interpreter like feature to generate report on the fly
