# Ontology Agent

## Description

The Ontology Agent is a core agent responsible for managing and interacting with the ontology system. It provides a natural language interface for searching, adding, and updating ontological data using an o3-mini model.

## Capabilities

- **Search Operations**: Search for existing entities and classes within the ontology.
- **Data Management**: Add and update individuals in triple store (Process BFO_0000015 are not supported yet).
- **Smart Validation**: Automatically checks for duplicates before adding new entries.

## Use Cases

### Search Classes
Search existing classes on ontology to help you build your ontology pipeline.

Examples:
- "What is the class for xxx?"
- "Please map this object "xxx" to an existing class in the ontology."

### Search Individuals
Search existing individuals for a given class.

Examples:
- "What are the individuals of class Person?"
- "Is there already a John Smith in the ontology?"

### Search Skills and People
Search existing skills and people in the ontology.

Examples:
- "Who has the skill of Python Programming?"
- "What are the skills of John Smith?"

### Search Organizations
Search existing organizations in the ontology.

Examples:
- "What is the organization for Microsoft?"
- "Is there already a LinkedIn page for Microsoft?"

### Search Websites and LinkedIn Pages
Search existing websites and LinkedIn pages in the ontology.

Examples:
- "What is the website of Microsoft?"
- "Is there already a LinkedIn page for Microsoft?"

### Add Individuals
Add new individuals to the ontology (without data properties or object properties). This is a non deterministic operation so a tool already exists to add a specific individual to the ontology, it will be used by the agent to add the individual to the ontology.

Examples:
- "Add John Smith as a person."
- "Add Microsoft as a commercial organization."

### Add/update person
Add or update person profiles with the following attributes:
- Name (required, must include first and last name)
- First name (automatically extracted from name)
- Last name (automatically extracted from name)
- Birth date (format: YYYY-MM-DD)
- LinkedIn page URL
- Skills (list of skill URIs)

Example: "Add John Smith with birth date 1990-01-01 and LinkedIn page https://linkedin.com/in/johnsmith"

### Add/update commercial organization
Add organization profiles with the following attributes:
- Name (required)
- Legal name
- Stock ticker
- Corporate website
- LinkedIn company page

Example: "Add Microsoft as a commercial organization with ticker MSFT and website https://microsoft.com"

### Add/update website
Add website information with:
- Website URL (required)
- Owner associations (people or organizations)

Example: "Add website https://example.com to Microsoft."

### Add/update LinkedIn page
Add LinkedIn page information with:
- LinkedIn URL (required, must match pattern: linkedin.com/(in|company|school)/...)
- LinkedIn ID (optional)
- LinkedIn public ID (extracted from URL)
- Owner associations (people or organizations)

Example: "Add LinkedIn page https://linkedin.com/company/microsoft"

### Add/update stock ticker
Add stock ticker information with:
- Ticker symbol (required, e.g., MSFT, AAPL)
- Organization association

Example: "Add ticker symbol MSFT for Microsoft"

### Add/update skills
Add professional skills with:
- Skill name (required)
- Description (optional)
- Person associations (list of people who have this skill)

Example: "Add Python Programming as a skill with description 'Programming in Python language'"