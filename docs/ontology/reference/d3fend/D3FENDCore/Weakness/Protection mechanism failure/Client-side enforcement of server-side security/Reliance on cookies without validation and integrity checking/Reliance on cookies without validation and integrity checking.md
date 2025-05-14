# Reliance on cookies without validation and integrity checking

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-565

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-565(Reliance<br>on<br>cookies<br>without<br>validation<br>and<br>integrity<br>checking):::d3fend-->d3fend.owl#CWE-602
    d3fend.owl#CWE-602(Client-side<br>enforcement<br>of<br>server-side<br>security):::d3fend-->d3fend.owl#CWE-693
    d3fend.owl#CWE-693(Protection<br>mechanism<br>failure):::d3fend-->d3fend.owl#Weakness
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
- [Protection mechanism failure](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Protection%20mechanism%20failure.md)
- [Client-side enforcement of server-side security](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Client-side%20enforcement%20of%20server-side%20security/Client-side%20enforcement%20of%20server-side%20security.md)
- [Reliance on cookies without validation and integrity checking](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Client-side%20enforcement%20of%20server-side%20security/Reliance%20on%20cookies%20without%20validation%20and%20integrity%20checking/Reliance%20on%20cookies%20without%20validation%20and%20integrity%20checking.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

