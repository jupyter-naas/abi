# Improper restriction of recursive entity references in dtds ('xml entity expansion')

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-776

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-776(Improper<br>restriction<br>of<br>recursive<br>entity<br>references<br>in<br>dtds<br>('xml<br>entity<br>expansion')):::d3fend-->d3fend.owl#CWE-674
    d3fend.owl#CWE-674(Uncontrolled<br>recursion):::d3fend-->d3fend.owl#CWE-834
    d3fend.owl#CWE-834(Excessive<br>iteration):::d3fend-->d3fend.owl#CWE-691
    d3fend.owl#CWE-691(Insufficient<br>control<br>flow<br>management):::d3fend-->d3fend.owl#Weakness
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
- [Insufficient control flow management](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Insufficient%20control%20flow%20management.md)
- [Excessive iteration](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Excessive%20iteration/Excessive%20iteration.md)
- [Uncontrolled recursion](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Excessive%20iteration/Uncontrolled%20recursion/Uncontrolled%20recursion.md)
- [Improper restriction of recursive entity references in dtds ('xml entity expansion')](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Excessive%20iteration/Uncontrolled%20recursion/Improper%20restriction%20of%20recursive%20entity%20references%20in%20dtds%20%28%27xml%20entity%20expansion%27%29/Improper%20restriction%20of%20recursive%20entity%20references%20in%20dtds%20%28%27xml%20entity%20expansion%27%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

