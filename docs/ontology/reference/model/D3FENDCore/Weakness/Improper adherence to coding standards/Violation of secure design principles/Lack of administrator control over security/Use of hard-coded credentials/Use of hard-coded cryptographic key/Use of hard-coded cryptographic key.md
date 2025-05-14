# Use of hard-coded cryptographic key

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-321

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-321(Use<br>of<br>hard-coded<br>cryptographic<br>key):::d3fend-->d3fend.owl#CWE-798
    d3fend.owl#CWE-798(Use<br>of<br>hard-coded<br>credentials):::d3fend-->d3fend.owl#CWE-671
    d3fend.owl#CWE-671(Lack<br>of<br>administrator<br>control<br>over<br>security):::d3fend-->d3fend.owl#CWE-657
    d3fend.owl#CWE-657(Violation<br>of<br>secure<br>design<br>principles):::d3fend-->d3fend.owl#CWE-710
    d3fend.owl#CWE-710(Improper<br>adherence<br>to<br>coding<br>standards):::d3fend-->d3fend.owl#Weakness
    d3fend.owl#Weakness(Weakness):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md)
- [Improper adherence to coding standards](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20adherence%20to%20coding%20standards.md)
- [Violation of secure design principles](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Violation%20of%20secure%20design%20principles.md)
- [Lack of administrator control over security](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Lack%20of%20administrator%20control%20over%20security/Lack%20of%20administrator%20control%20over%20security.md)
- [Use of hard-coded credentials](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Lack%20of%20administrator%20control%20over%20security/Use%20of%20hard-coded%20credentials/Use%20of%20hard-coded%20credentials.md)
- [Use of hard-coded cryptographic key](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Lack%20of%20administrator%20control%20over%20security/Use%20of%20hard-coded%20credentials/Use%20of%20hard-coded%20cryptographic%20key/Use%20of%20hard-coded%20cryptographic%20key.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

