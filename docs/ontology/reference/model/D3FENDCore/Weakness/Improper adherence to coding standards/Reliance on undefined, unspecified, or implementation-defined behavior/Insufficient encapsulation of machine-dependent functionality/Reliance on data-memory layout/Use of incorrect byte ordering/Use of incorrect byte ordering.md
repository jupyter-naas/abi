# Use of incorrect byte ordering

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-198

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-198(Use<br>of<br>incorrect<br>byte<br>ordering):::d3fend-->d3fend.owl#CWE-188
    d3fend.owl#CWE-188(Reliance<br>on<br>data-memory<br>layout):::d3fend-->d3fend.owl#CWE-1105
    d3fend.owl#CWE-1105(Insufficient<br>encapsulation<br>of<br>machine-dependent<br>functionality):::d3fend-->d3fend.owl#CWE-758
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
- [Insufficient encapsulation of machine-dependent functionality](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Insufficient%20encapsulation%20of%20machine-dependent%20functionality/Insufficient%20encapsulation%20of%20machine-dependent%20functionality.md)
- [Reliance on data-memory layout](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Insufficient%20encapsulation%20of%20machine-dependent%20functionality/Reliance%20on%20data-memory%20layout/Reliance%20on%20data-memory%20layout.md)
- [Use of incorrect byte ordering](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Reliance%20on%20undefined%2C%20unspecified%2C%20or%20implementation-defined%20behavior/Insufficient%20encapsulation%20of%20machine-dependent%20functionality/Reliance%20on%20data-memory%20layout/Use%20of%20incorrect%20byte%20ordering/Use%20of%20incorrect%20byte%20ordering.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

