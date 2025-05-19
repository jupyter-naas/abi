# Call to non-ubiquitous api

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-589

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-589(Call<br>to<br>non-ubiquitous<br>api):::d3fend-->d3fend.owl#CWE-474
    d3fend.owl#CWE-474(Use<br>of<br>function<br>with<br>inconsistent<br>implementations):::d3fend-->d3fend.owl#CWE-758
    d3fend.owl#CWE-758(Reliance<br>on<br>undefined,<br>unspecified,<br>or<br>implementation-defined<br>behavior):::d3fend-->d3fend.owl#CWE-710
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
- [Reliance on undefined, unspecified, or implementation-defined behavior](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior.md)
- [Use of function with inconsistent implementations](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Use%20of%20function%20with%20inconsistent%20implementations/Use%20of%20function%20with%20inconsistent%20implementations.md)
- [Call to non-ubiquitous api](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Use%20of%20function%20with%20inconsistent%20implementations/Call%20to%20non-ubiquitous%20api/Call%20to%20non-ubiquitous%20api.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

