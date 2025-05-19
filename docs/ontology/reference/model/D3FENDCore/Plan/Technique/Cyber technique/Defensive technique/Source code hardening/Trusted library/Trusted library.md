# Trusted library

## Overview

### Definition
A trusted library is a collection of pre-verified and secure code modules or components that are used within software applications to perform specific functions. These libraries are considered reliable and have been vetted for security vulnerabilities, ensuring they do not introduce risks into the application.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#TrustedLibrary

### Subclass Of
```mermaid
graph BT
    d3fend.owl#TrustedLibrary(Trusted<br>library):::d3fend-->d3fend.owl#SourceCodeHardening
    d3fend.owl#SourceCodeHardening(Source<br>code<br>hardening):::d3fend-->d3fend.owl#DefensiveTechnique
    d3fend.owl#DefensiveTechnique(Defensive<br>technique):::d3fend-->d3fend.owl#CyberTechnique
    d3fend.owl#CyberTechnique(Cyber<br>technique):::d3fend-->d3fend.owl#Technique
    d3fend.owl#Technique(Technique):::d3fend-->d3fend.owl#Plan
    d3fend.owl#Plan(Plan):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Plan](/docs/ontology/reference/model/D3FENDCore/Plan/Plan.md)
- [Technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Technique.md)
- [Cyber technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Cyber%20technique.md)
- [Defensive technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Defensive%20technique.md)
- [Source code hardening](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Source%20code%20hardening/Source%20code%20hardening.md)
- [Trusted library](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Cyber%20technique/Defensive%20technique/Source%20code%20hardening/Trusted%20library/Trusted%20library.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
