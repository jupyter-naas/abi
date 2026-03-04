# Ontologies in ABI

## What are Ontologies?

Ontologies in ABI provide a formal representation of knowledge using semantic web technologies. They define:

- **Classes/Concepts**: Categories of entities (e.g., Person, Organization, Event)
- **Properties**: Relationships between entities or attributes of entities
- **Individuals**: Specific instances of classes
- **Rules/Axioms**: Logical constraints that govern relationships

ABI uses RDF (Resource Description Framework) and OWL (Web Ontology Language) to represent ontologies in a machine-readable format.

## Ontology Organization

Ontologies in ABI are organized in a layered approach:

1. **Foundation or Top-Level Ontologies**: Basic concepts like space, time, and objects (e.g., BFO - Basic Formal Ontology)
2. **Mid-Level Ontologies**: Concepts common across domains (e.g., Common Core Ontologies)
3. **Domain Ontologies**: Concepts specific to particular domains (e.g., Finance, Healthcare)
4. **Application Ontologies**: Concepts specific to applications

The `src/core/ontology/ontologies/` directory contains the vetted ontologies used across ABI.

## Creating Module Ontologies

When building a module, you can:

1. **Reuse existing ontologies**: Leverage foundation and mid-level ontologies
2. **Extend with domain concepts**: Add domain-specific classes and properties
3. **Create application ontologies**: Define concepts specific to your module

### File Structure

Ontologies can be placed in your module's directory: 

```
src/custom/modules/your_module_name/
└── ontologies/
├── YourDomainOntology.ttl # Domain-level ontology
└── YourApplicationOntology.ttl # Application-specific ontology
```

### Automatic Loading of Ontologies

Ontologies placed in your module's `ontologies/` directory are automatically loaded when ABI starts up. The system:

1. Reads all module definitions
2. For each module, loads all ontology files listed in the module's `ontologies` list attribute
3. Adds them to the triple store using `services.triple_store_service.load_schema()`

#### Schema Management

When a turtle file is loaded:

1. **First-time Loading**: 
   - The entire file is parsed and added to the triple store
   - A schema record is created with metadata including file path, content hash, and timestamp
   - The content is stored in base64 format for future comparisons

2. **Updating Existing Files**:
   - When ABI starts, it checks the hash of each ontology file
   - If unchanged, the file is skipped
   - If changed, it:
     - Compares the old and new versions to determine additions and deletions
     - Adds only the new triples and removes only the deleted ones
     - Updates the stored hash, timestamp, and content

This incremental update approach ensures that only the necessary changes are applied to the triple store, making the system more efficient when handling large ontologies.

### Creating an Ontology File

Ontology files use mostly Turtle (.ttl) format:

```t
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix cco: <https://www.commoncoreontologies.org/> .
@prefix abi: <http://ontology.naas.ai/abi/> .

<http://ontology.naas.ai/abi/linkedin.ttl> rdf:type owl:Ontology ;
                                        owl:imports <> ;
                                        owl:versionIRI <https://github.com/jupyter-naas/abi/tree/cli/src/ontologies/application-level/linkedin.ttl> ;
                                        dc11:contributor "Jeremy Ravenel" , "Maxime Jublou" , "Florent Ravenel" ;
                                        dc:description "Application ontology for LinkedIn."@en ;
                                        dc:license "" ;
                                        dc:title "LinkedIn Application Ontology" .

#################################################################
#    Classes
#################################################################

abi:LinkedInPage a owl:Class ;
    rdfs:subClassOf cco:ont00001069 ; # Representational Information Content Entity
    rdfs:label "LinkedIn Page" ;
    skos:definition "A LinkedIn page that represents an entity's presence on LinkedIn, containing information specific to that entity type such as professional details, organizational information, or educational programs." ;
    skos:example "A LinkedIn page could be a profile page showing work experience, a company page with job postings, or a school page highlighting academic programs." ;
    rdfs:comment "A LinkedIn page must be registered in https://www.linkedin.com/" .

abi:LinkedInProfilePage a owl:Class ;
    rdfs:subClassOf abi:LinkedInPage ;
    rdfs:label "LinkedIn Profile Page" ;
    skos:definition "A LinkedIn profile page that includes information such as a person's professional history, skills, and endorsements, representing the individual's professional identity on the web." ;
    skos:example "John Doe's LinkedIn profile page, which lists his work experience at various companies, skills such as programming and data analysis, and endorsements from colleagues." ;
    rdfs:comment "A LinkedIn profile page must be registered in https://www.linkedin.com/in/" .

abi:LinkedInCompanyPage a owl:Class ;
    rdfs:subClassOf abi:LinkedInPage ;
    rdfs:label "LinkedIn Company Page" ;
    skos:definition "A LinkedIn company page that includes information such as the company's overview, products/services, job postings, and updates, representing the organization's professional presence on LinkedIn." ;
    skos:example "Microsoft's LinkedIn company page, which showcases their company information, latest news, job opportunities, and employee insights." ;
    rdfs:comment "A LinkedIn company page must be registered in https://www.linkedin.com/company/" .

abi:LinkedInSchoolPage a owl:Class ;
    rdfs:subClassOf abi:LinkedInPage ;
    rdfs:label "LinkedIn School Page" ;
    skos:definition "A LinkedIn school page that includes information about the school's programs, faculty, students, and events, representing the educational institution's professional presence on LinkedIn." ;
    rdfs:comment "A LinkedIn school page must be registered in https://www.linkedin.com/school/" .

#################################################################
#    Object Properties
#################################################################

abi:hasLinkedInPage a owl:ObjectProperty ;
    rdfs:domain [ rdf:type owl:Class ;
                  owl:unionOf ( cco:ont00001180
                               cco:ont00001262
                             )
                ] ;
    rdfs:range abi:LinkedInPage ;
    owl:inverseOf abi:isLinkedInPageOf ;
    rdfs:label "has LinkedIn Page"@en ;
    skos:definition "Relates an entity to its LinkedIn page."@en ;
    skos:example "John Doe's LinkedIn profile page, which lists his work experience at various companies, skills such as programming and data analysis, and endorsements from colleagues."@en .

abi:isLinkedInPageOf a owl:ObjectProperty ;
    rdfs:domain abi:LinkedInPage ;
    rdfs:range [ rdf:type owl:Class ;
                 owl:unionOf ( cco:ont00001180
                              cco:ont00001262
                            )
               ] ;
    owl:inverseOf abi:hasLinkedInPage ;
    rdfs:label "is LinkedIn Page of"@en ;
    skos:definition "Relates a LinkedIn page to the entity it represents."@en ;
    skos:example "A LinkedIn profile page that represents John Doe's professional presence."@en .

#################################################################
#    Data properties
#################################################################

abi:linkedin_id a owl:DatatypeProperty ;
    rdfs:domain abi:LinkedInPage ;
    rdfs:range xsd:string ;
    rdfs:label "LinkedIn ID"@en ;
    skos:definition "The ID of the LinkedIn page."@en ;
    skos:example "The unique ID of John Doe's LinkedIn profile page is 'ACoAAAa5py0Bzrp5_7OmHIsNP6xxxxxxxx'."@en .

abi:linkedin_url a owl:DatatypeProperty ;
    rdfs:domain abi:LinkedInPage ;
    rdfs:range xsd:string ;
    rdfs:label "LinkedIn URL"@en ;
    skos:definition "The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."@en ;
    skos:example "The URL of John Doe's LinkedIn profile page is 'https://www.linkedin.com/in/ACoAAAa5py0Bzrp5_7OmHIsNP6xxxxxxxx'."@en .

abi:linkedin_public_id a owl:DatatypeProperty ;
    rdfs:domain abi:LinkedInPage ;
    rdfs:range xsd:string ;
    rdfs:label "LinkedIn Public ID"@en ;
    skos:definition "The public ID of the LinkedIn page. It might change over time."@en ;
    skos:example "The public ID of John Doe's LinkedIn profile page is 'johndoe'."@en .

abi:linkedin_public_url a owl:DatatypeProperty ;
    rdfs:domain abi:LinkedInPage ;
    rdfs:range xsd:string ;
    rdfs:label "LinkedIn Public URL"@en ;
    skos:definition "The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."@en ;
    skos:example "The public URL of John Doe's LinkedIn profile page is 'https://www.linkedin.com/in/johndoe'."@en .
```

## Ontology Best Practices

1. **Start with existing ontologies**: Avoid reinventing concepts that already exist
2. **Follow upper ontology principles**: Align with foundation ontologies like BFO
3. **Use consistent naming**: Follow the pattern `ClassNamesInPascalCase`, `propertyNamesInCamelCase`, `datapropertyinlowercase`
4. **Add documentation**: Include rdfs:label, skos:definition, skos:example for all classes and rdfs:domain, rdfs:range for all properties
5. **Keep it modular**: Separate domain concepts from application-specific ones
6. **Test with reasoners**: Validate your ontology for consistency
7. **Maintain compatibility**: Ensure backward compatibility when updating